"""
VestaCode Spatial Intelligence Engine
======================================
A deterministic geometry engine that validates and corrects BIM layouts
using pure math — no LLM required. This is the "physics brain" of VestaCode.

Systems:
    1. AABB Collision Detection — prevents furniture overlap
    2. Wall Snapping — aligns furniture to nearest wall normal
    3. Clearance Zone Enforcement — ensures ergonomic buffers around doors/paths
    4. NavMesh Pathfinding (A*) — validates human walkability between rooms
    5. Ergonomic Flow Analysis — scores the overall spatial quality
"""

import math
import heapq
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from backend.core.bim_state import BIMProjectState, BIMElement, ObjectType, Vector3


# ============================================================================
#  DATA STRUCTURES
# ============================================================================

@dataclass
class AABB:
    """Axis-Aligned Bounding Box for 2D collision detection (top-down view)."""
    min_x: float
    min_z: float
    max_x: float
    max_z: float

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.min_x + self.max_x) / 2, (self.min_z + self.max_z) / 2)

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_z - self.min_z

    @property
    def area(self) -> float:
        return self.width * self.depth

    def intersects(self, other: 'AABB') -> bool:
        """Check if two AABBs overlap."""
        return (self.min_x < other.max_x and self.max_x > other.min_x and
                self.min_z < other.max_z and self.max_z > other.min_z)

    def overlap_area(self, other: 'AABB') -> float:
        """Calculate the overlap area between two AABBs."""
        if not self.intersects(other):
            return 0.0
        dx = min(self.max_x, other.max_x) - max(self.min_x, other.min_x)
        dz = min(self.max_z, other.max_z) - max(self.min_z, other.min_z)
        return max(0, dx) * max(0, dz)

    def contains_point(self, x: float, z: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_z <= z <= self.max_z

    def expanded(self, margin: float) -> 'AABB':
        """Return a new AABB expanded by a margin on all sides."""
        return AABB(
            self.min_x - margin,
            self.min_z - margin,
            self.max_x + margin,
            self.max_z + margin
        )

    def distance_to(self, other: 'AABB') -> float:
        """Minimum distance between two AABBs (0 if overlapping)."""
        dx = max(0, max(self.min_x - other.max_x, other.min_x - self.max_x))
        dz = max(0, max(self.min_z - other.max_z, other.min_z - self.max_z))
        return math.sqrt(dx * dx + dz * dz)


@dataclass
class SpatialIssue:
    """A detected spatial problem."""
    severity: str       # "critical", "warning", "info"
    issue_type: str     # "collision", "clearance", "flow", "snap"
    element_ids: List[str]
    description: str
    auto_fix_applied: bool = False
    fix_description: str = ""


@dataclass
class FlowNode:
    """A node in the navigation graph."""
    x: float
    z: float
    walkable: bool = True
    element_id: Optional[str] = None


@dataclass
class SpatialReport:
    """Full spatial analysis report."""
    issues: List[SpatialIssue] = field(default_factory=list)
    flow_score: float = 0.0               # 0-100
    collision_count: int = 0
    clearance_violations: int = 0
    blocked_paths: int = 0
    total_furniture_area: float = 0.0
    total_room_area: float = 0.0
    density_ratio: float = 0.0            # furniture_area / room_area
    nav_graph_nodes: int = 0
    corrections_applied: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_score": round(self.flow_score, 1),
            "collision_count": self.collision_count,
            "clearance_violations": self.clearance_violations,
            "blocked_paths": self.blocked_paths,
            "density_ratio": round(self.density_ratio, 3),
            "corrections_applied": self.corrections_applied,
            "issues": [
                {
                    "severity": i.severity,
                    "type": i.issue_type,
                    "elements": i.element_ids,
                    "description": i.description,
                    "auto_fixed": i.auto_fix_applied,
                    "fix": i.fix_description
                }
                for i in self.issues
            ]
        }


# ============================================================================
#  SPATIAL ENGINE
# ============================================================================

class SpatialEngine:
    """
    The deterministic spatial intelligence core.
    Operates on pure geometry — no LLM calls.
    """

    # Ergonomic constants (meters)
    MIN_WALKING_PATH = 0.90       # 36 inches — ADA minimum clear width
    DOOR_SWING_CLEARANCE = 1.20   # Full arc radius for a standard door
    WINDOW_ACCESS_DEPTH = 0.60    # Min clearance in front of a window
    FURNITURE_GAP_MIN = 0.15      # Min gap between two pieces of furniture
    WALL_SNAP_THRESHOLD = 0.30    # Snap to wall if within 30cm
    MAX_DENSITY_RATIO = 0.55      # Max 55% of floor covered by furniture

    # NavMesh grid resolution
    GRID_CELL_SIZE = 0.25         # 25cm grid cells for pathfinding

    def __init__(self):
        self._walls: List[Tuple[str, AABB]] = []
        self._doors: List[Tuple[str, AABB]] = []
        self._windows: List[Tuple[str, AABB]] = []
        self._furniture: List[Tuple[str, AABB]] = []
        self._all_boxes: Dict[str, AABB] = {}
        self._room_bounds: AABB = AABB(0, 0, 1, 1)

    # -----------------------------------------------------------------------
    #  SETUP
    # -----------------------------------------------------------------------

    def _element_to_aabb(self, el: BIMElement) -> AABB:
        """Convert a BIMElement to its Axis-Aligned Bounding Box."""
        half_x = el.dimensions.x / 2
        half_z = el.dimensions.z / 2
        return AABB(
            min_x=el.position.x - half_x,
            min_z=el.position.z - half_z,
            max_x=el.position.x + half_x,
            max_z=el.position.z + half_z
        )

    def _index_elements(self, project: BIMProjectState):
        """Categorize all BIM elements into spatial buckets."""
        self._walls.clear()
        self._doors.clear()
        self._windows.clear()
        self._furniture.clear()
        self._all_boxes.clear()

        for el in project.elements:
            box = self._element_to_aabb(el)
            self._all_boxes[el.id] = box
            if el.type == ObjectType.WALL:
                self._walls.append((el.id, box))
            elif el.type == ObjectType.DOOR:
                self._doors.append((el.id, box))
            elif el.type == ObjectType.WINDOW:
                self._windows.append((el.id, box))
            elif el.type == ObjectType.FURNITURE:
                self._furniture.append((el.id, box))

        # Calculate room bounds from all walls
        if self._walls:
            all_min_x = min(b.min_x for _, b in self._walls)
            all_min_z = min(b.min_z for _, b in self._walls)
            all_max_x = max(b.max_x for _, b in self._walls)
            all_max_z = max(b.max_z for _, b in self._walls)
            self._room_bounds = AABB(all_min_x, all_min_z, all_max_x, all_max_z)

    # -----------------------------------------------------------------------
    #  1. COLLISION DETECTION
    # -----------------------------------------------------------------------

    def _detect_collisions(self) -> List[SpatialIssue]:
        """Check all furniture pairs and furniture-vs-wall for overlaps."""
        issues = []

        # Furniture vs Furniture
        for i in range(len(self._furniture)):
            for j in range(i + 1, len(self._furniture)):
                id_a, box_a = self._furniture[i]
                id_b, box_b = self._furniture[j]
                overlap = box_a.overlap_area(box_b)
                if overlap > 0.01:  # More than 1cm² overlap
                    issues.append(SpatialIssue(
                        severity="critical",
                        issue_type="collision",
                        element_ids=[id_a, id_b],
                        description=f"Furniture overlap detected ({overlap:.2f}m²). "
                                    f"Items are physically intersecting."
                    ))

        # Furniture vs Wall
        for fid, fbox in self._furniture:
            for wid, wbox in self._walls:
                overlap = fbox.overlap_area(wbox)
                if overlap > 0.01:
                    issues.append(SpatialIssue(
                        severity="warning",
                        issue_type="collision",
                        element_ids=[fid, wid],
                        description=f"Furniture intersects wall ({overlap:.2f}m²). "
                                    f"Item may be partially inside the wall."
                    ))

        return issues

    # -----------------------------------------------------------------------
    #  2. WALL SNAPPING
    # -----------------------------------------------------------------------

    def _snap_to_walls(self, project: BIMProjectState) -> List[SpatialIssue]:
        """Snap furniture that is close to a wall to align flush against it."""
        issues = []
        el_map = {el.id: el for el in project.elements}

        for fid, fbox in self._furniture:
            furniture_el = el_map.get(fid)
            if not furniture_el:
                continue

            best_wall = None
            best_dist = float('inf')
            best_axis = None  # 'x' or 'z'
            best_direction = 0  # -1 or +1

            for wid, wbox in self._walls:
                # Check if this is a "thin" wall (identify its primary axis)
                wall_is_horizontal = wbox.depth < wbox.width  # runs along X
                wall_is_vertical = wbox.width < wbox.depth    # runs along Z

                if wall_is_horizontal:
                    # Only snap if furniture is within the wall's X extent (with some margin)
                    margin = 0.5
                    if fbox.max_x < wbox.min_x - margin or fbox.min_x > wbox.max_x + margin:
                        continue
                    # Check distance from furniture bottom/top to wall Z center
                    wall_z = (wbox.min_z + wbox.max_z) / 2
                    dist_bottom = abs(fbox.min_z - wall_z)
                    dist_top = abs(fbox.max_z - wall_z)
                    min_dist = min(dist_bottom, dist_top)
                    if min_dist < best_dist and min_dist < self.WALL_SNAP_THRESHOLD:
                        best_dist = min_dist
                        best_wall = wbox
                        best_axis = 'z'
                        best_direction = 1 if dist_bottom < dist_top else -1

                elif wall_is_vertical:
                    # Only snap if furniture is within the wall's Z extent (with some margin)
                    margin = 0.5
                    if fbox.max_z < wbox.min_z - margin or fbox.min_z > wbox.max_z + margin:
                        continue
                    # Check distance from furniture left/right to wall X center
                    wall_x = (wbox.min_x + wbox.max_x) / 2
                    dist_left = abs(fbox.min_x - wall_x)
                    dist_right = abs(fbox.max_x - wall_x)
                    min_dist = min(dist_left, dist_right)
                    if min_dist < best_dist and min_dist < self.WALL_SNAP_THRESHOLD:
                        best_dist = min_dist
                        best_wall = wbox
                        best_axis = 'x'
                        best_direction = 1 if dist_left < dist_right else -1

            if best_wall and best_dist > 0.02:  # Only snap if not already flush
                half_wall_thickness = max(best_wall.width, best_wall.depth) / 2
                if best_axis == 'z':
                    wall_edge = (best_wall.min_z + best_wall.max_z) / 2
                    half_furniture = furniture_el.dimensions.z / 2
                    new_z = wall_edge + (half_furniture + half_wall_thickness) * best_direction
                    old_z = furniture_el.position.z
                    furniture_el.position.z = new_z
                    issues.append(SpatialIssue(
                        severity="info",
                        issue_type="snap",
                        element_ids=[fid],
                        description=f"Snapped to wall (Z: {old_z:.2f} → {new_z:.2f}, Δ={abs(new_z-old_z):.2f}m).",
                        auto_fix_applied=True,
                        fix_description=f"Aligned Z-axis to nearest wall face."
                    ))
                elif best_axis == 'x':
                    wall_edge = (best_wall.min_x + best_wall.max_x) / 2
                    half_furniture = furniture_el.dimensions.x / 2
                    new_x = wall_edge + (half_furniture + half_wall_thickness) * best_direction
                    old_x = furniture_el.position.x
                    furniture_el.position.x = new_x
                    issues.append(SpatialIssue(
                        severity="info",
                        issue_type="snap",
                        element_ids=[fid],
                        description=f"Snapped to wall (X: {old_x:.2f} → {new_x:.2f}, Δ={abs(new_x-old_x):.2f}m).",
                        auto_fix_applied=True,
                        fix_description=f"Aligned X-axis to nearest wall face."
                    ))

        return issues

    # -----------------------------------------------------------------------
    #  3. CLEARANCE ZONE ENFORCEMENT
    # -----------------------------------------------------------------------

    def _check_clearance_zones(self) -> List[SpatialIssue]:
        """Ensure no furniture is placed inside critical clearance zones."""
        issues = []

        for did, dbox in self._doors:
            # Create a clearance zone around the door (swing arc)
            clearance = dbox.expanded(self.DOOR_SWING_CLEARANCE)
            for fid, fbox in self._furniture:
                if clearance.intersects(fbox):
                    overlap = clearance.overlap_area(fbox)
                    if overlap > 0.05:  # Significant encroachment
                        issues.append(SpatialIssue(
                            severity="critical",
                            issue_type="clearance",
                            element_ids=[fid, did],
                            description=f"Furniture blocks door swing arc "
                                        f"({overlap:.2f}m² encroachment). "
                                        f"Min clearance: {self.DOOR_SWING_CLEARANCE}m.",
                        ))

        for wid, wbox in self._windows:
            # Create a smaller clearance zone in front of windows
            clearance = wbox.expanded(self.WINDOW_ACCESS_DEPTH)
            for fid, fbox in self._furniture:
                if clearance.intersects(fbox):
                    overlap = clearance.overlap_area(fbox)
                    if overlap > 0.1:
                        issues.append(SpatialIssue(
                            severity="warning",
                            issue_type="clearance",
                            element_ids=[fid, wid],
                            description=f"Furniture obstructs window access "
                                        f"({overlap:.2f}m² encroachment). "
                                        f"Min clearance: {self.WINDOW_ACCESS_DEPTH}m.",
                        ))

        return issues

    # -----------------------------------------------------------------------
    #  4. NAVMESH PATHFINDING (A*)
    # -----------------------------------------------------------------------

    def _build_nav_grid(self) -> Tuple[List[List[bool]], float, float, int, int]:
        """Build a 2D walkability grid from the room bounds."""
        bounds = self._room_bounds
        cell = self.GRID_CELL_SIZE

        cols = max(1, int(math.ceil(bounds.width / cell)))
        rows = max(1, int(math.ceil(bounds.depth / cell)))

        # Initialize all cells as walkable
        grid = [[True] * cols for _ in range(rows)]

        # Mark wall and furniture cells as non-walkable
        obstacles = self._walls + self._furniture
        for oid, obox in obstacles:
            # Convert AABB to grid coordinates
            col_start = max(0, int((obox.min_x - bounds.min_x) / cell))
            col_end = min(cols - 1, int((obox.max_x - bounds.min_x) / cell))
            row_start = max(0, int((obox.min_z - bounds.min_z) / cell))
            row_end = min(rows - 1, int((obox.max_z - bounds.min_z) / cell))

            for r in range(row_start, row_end + 1):
                for c in range(col_start, col_end + 1):
                    grid[r][c] = False

        return grid, bounds.min_x, bounds.min_z, rows, cols

    def _astar(self, grid: List[List[bool]], start: Tuple[int, int],
               goal: Tuple[int, int], rows: int, cols: int) -> Optional[List[Tuple[int, int]]]:
        """A* pathfinding on the nav grid."""
        if not grid[start[0]][start[1]] or not grid[goal[0]][goal[1]]:
            return None  # Start or goal is blocked

        open_set: List[Tuple[float, Tuple[int, int]]] = []
        heapq.heappush(open_set, (0, start))
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0}

        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
            return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

        # 8-directional movement
        directions = [
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        ]

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                return list(reversed(path))

            for dr, dc in directions:
                nr, nc = current[0] + dr, current[1] + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc]:
                    # Diagonal cost is sqrt(2), orthogonal is 1
                    move_cost = 1.414 if dr != 0 and dc != 0 else 1.0
                    tentative_g = g_score[current] + move_cost

                    neighbor = (nr, nc)
                    if tentative_g < g_score.get(neighbor, float('inf')):
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f_score = tentative_g + heuristic(neighbor, goal)
                        heapq.heappush(open_set, (f_score, neighbor))

        return None  # No path found

    def _check_pathfinding(self) -> Tuple[List[SpatialIssue], int]:
        """Validate that all door-to-door paths are walkable."""
        issues = []
        nav_nodes = 0

        if len(self._doors) < 2:
            return issues, 0

        grid, origin_x, origin_z, rows, cols = self._build_nav_grid()
        nav_nodes = sum(sum(1 for c in row if c) for row in grid)
        cell = self.GRID_CELL_SIZE

        # Convert door positions to grid coordinates
        door_cells = []
        for did, dbox in self._doors:
            cx, cz = dbox.center
            col = min(cols - 1, max(0, int((cx - origin_x) / cell)))
            row = min(rows - 1, max(0, int((cz - origin_z) / cell)))
            # Find nearest walkable cell if door cell is blocked
            if not grid[row][col]:
                found = False
                for radius in range(1, 5):
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            nr, nc = row + dr, col + dc
                            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc]:
                                row, col = nr, nc
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
            door_cells.append((did, (row, col)))

        # Check paths between all door pairs
        blocked_count = 0
        for i in range(len(door_cells)):
            for j in range(i + 1, len(door_cells)):
                did_a, cell_a = door_cells[i]
                did_b, cell_b = door_cells[j]
                path = self._astar(grid, cell_a, cell_b, rows, cols)
                if path is None:
                    blocked_count += 1
                    issues.append(SpatialIssue(
                        severity="critical",
                        issue_type="flow",
                        element_ids=[did_a, did_b],
                        description=f"No walkable path between doors. "
                                    f"Furniture arrangement blocks human egress route.",
                    ))

        return issues, nav_nodes

    # -----------------------------------------------------------------------
    #  5. DENSITY & FLOW SCORING
    # -----------------------------------------------------------------------

    def _calculate_density(self) -> Tuple[float, float, float]:
        """Calculate furniture density ratio."""
        room_area = self._room_bounds.area
        if room_area <= 0:
            return 0, 0, 0

        furniture_area = sum(b.area for _, b in self._furniture)
        ratio = furniture_area / room_area
        return furniture_area, room_area, ratio

    def _calculate_flow_score(self, report: SpatialReport) -> float:
        """
        Calculate overall spatial quality score (0-100).
        
        Scoring (rebalanced for multi-room layouts):
            - Start at 100
            - Critical collision:      -12 each (max 3 counted)
            - Warning collision:       -2  each (max 5 counted)
            - Clearance violation:     -3  each (max 8 counted)
            - Blocked path:            -20 each
            - Over-density:            -10
            - Each auto-fix applied:   +3 (recovery credit, max +15)
        """
        score = 100.0

        critical_collisions = 0
        warning_collisions = 0
        clearance_count = 0

        for issue in report.issues:
            if issue.issue_type == "collision" and issue.severity == "critical":
                critical_collisions += 1
                if critical_collisions <= 3:
                    score -= 12
            elif issue.issue_type == "collision" and issue.severity == "warning":
                warning_collisions += 1
                if warning_collisions <= 5:
                    score -= 2
            elif issue.issue_type == "clearance":
                clearance_count += 1
                if clearance_count <= 8:
                    score -= 3
            elif issue.issue_type == "flow":
                score -= 20

        if report.density_ratio > self.MAX_DENSITY_RATIO:
            score -= 10

        score += min(report.corrections_applied * 3, 15)

        return max(0.0, min(100.0, score))

    # -----------------------------------------------------------------------
    #  6. COLLISION RESOLUTION (Auto-Fix)
    # -----------------------------------------------------------------------

    def _resolve_collisions(self, project: BIMProjectState) -> List[SpatialIssue]:
        """Attempt to auto-fix furniture-furniture collisions by nudging."""
        issues = []
        el_map = {el.id: el for el in project.elements}

        for i in range(len(self._furniture)):
            for j in range(i + 1, len(self._furniture)):
                id_a, box_a = self._furniture[i]
                id_b, box_b = self._furniture[j]

                if not box_a.intersects(box_b):
                    continue

                overlap_x = min(box_a.max_x, box_b.max_x) - max(box_a.min_x, box_b.min_x)
                overlap_z = min(box_a.max_z, box_b.max_z) - max(box_a.min_z, box_b.min_z)

                el_b = el_map.get(id_b)
                if not el_b:
                    continue

                # Push the second element along the axis of least overlap
                nudge = self.FURNITURE_GAP_MIN
                if overlap_x < overlap_z:
                    # Nudge along X
                    direction = 1 if box_b.center[0] >= box_a.center[0] else -1
                    el_b.position.x += (overlap_x + nudge) * direction
                    issues.append(SpatialIssue(
                        severity="info",
                        issue_type="collision",
                        element_ids=[id_a, id_b],
                        description=f"Auto-resolved collision. Nudged {id_b} by "
                                    f"{(overlap_x + nudge) * direction:+.2f}m on X-axis.",
                        auto_fix_applied=True,
                        fix_description="Separated overlapping furniture along X-axis."
                    ))
                else:
                    # Nudge along Z
                    direction = 1 if box_b.center[1] >= box_a.center[1] else -1
                    el_b.position.z += (overlap_z + nudge) * direction
                    issues.append(SpatialIssue(
                        severity="info",
                        issue_type="collision",
                        element_ids=[id_a, id_b],
                        description=f"Auto-resolved collision. Nudged {id_b} by "
                                    f"{(overlap_z + nudge) * direction:+.2f}m on Z-axis.",
                        auto_fix_applied=True,
                        fix_description="Separated overlapping furniture along Z-axis."
                    ))

        return issues

    # -----------------------------------------------------------------------
    #  MAIN ANALYSIS PIPELINE
    # -----------------------------------------------------------------------

    def analyze(self, project: BIMProjectState, auto_fix: bool = True) -> SpatialReport:
        """
        Run the full spatial analysis pipeline.

        Args:
            project: The BIM project to analyze.
            auto_fix: If True, automatically correct minor issues (snapping, nudging).

        Returns:
            SpatialReport with all findings and corrections.
        """
        report = SpatialReport()

        # 1. Index all elements
        self._index_elements(project)

        if not self._furniture and not self._walls:
            report.flow_score = 100
            return report

        # 2. Wall Snapping (runs first to improve subsequent checks)
        if auto_fix and self._furniture and self._walls:
            snap_issues = self._snap_to_walls(project)
            report.issues.extend(snap_issues)
            report.corrections_applied += sum(1 for i in snap_issues if i.auto_fix_applied)
            # Re-index after snapping
            self._index_elements(project)

        # 3. Collision Detection
        collision_issues = self._detect_collisions()
        report.issues.extend(collision_issues)
        report.collision_count = len(collision_issues)

        # 4. Auto-Fix Collisions
        if auto_fix and report.collision_count > 0:
            fix_issues = self._resolve_collisions(project)
            report.issues.extend(fix_issues)
            report.corrections_applied += sum(1 for i in fix_issues if i.auto_fix_applied)
            # Re-index and re-check
            self._index_elements(project)
            remaining = self._detect_collisions()
            report.collision_count = len(remaining)

        # 5. Clearance Zones
        clearance_issues = self._check_clearance_zones()
        report.issues.extend(clearance_issues)
        report.clearance_violations = len(clearance_issues)

        # 6. Pathfinding
        flow_issues, nav_nodes = self._check_pathfinding()
        report.issues.extend(flow_issues)
        report.blocked_paths = len(flow_issues)
        report.nav_graph_nodes = nav_nodes

        # 7. Density Analysis
        furniture_area, room_area, density = self._calculate_density()
        report.total_furniture_area = furniture_area
        report.total_room_area = room_area
        report.density_ratio = density

        if density > self.MAX_DENSITY_RATIO:
            report.issues.append(SpatialIssue(
                severity="warning",
                issue_type="density",
                element_ids=[],
                description=f"Room is over-furnished. Density ratio: {density:.1%} "
                            f"(max recommended: {self.MAX_DENSITY_RATIO:.0%}). "
                            f"Furniture: {furniture_area:.1f}m², Room: {room_area:.1f}m²."
            ))

        # 8. Calculate Flow Score
        report.flow_score = self._calculate_flow_score(report)

        return report


# ============================================================================
#  INTEGRATION HELPER
# ============================================================================

def run_spatial_analysis(project: BIMProjectState, auto_fix: bool = True) -> Dict[str, Any]:
    """
    Convenience function to run the spatial engine on a BIM project.
    Returns the report as a dictionary.
    """
    engine = SpatialEngine()
    report = engine.analyze(project, auto_fix=auto_fix)

    print(f"   📐 Spatial Engine: Score={report.flow_score}/100 | "
          f"Collisions={report.collision_count} | "
          f"Clearance={report.clearance_violations} | "
          f"Blocked={report.blocked_paths} | "
          f"Fixes={report.corrections_applied} | "
          f"Density={report.density_ratio:.1%}")

    return report.to_dict()
