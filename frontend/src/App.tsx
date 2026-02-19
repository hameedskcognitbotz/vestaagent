import React, { Suspense, useRef, useState, useEffect, useCallback } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, PerspectiveCamera, Environment, ContactShadows, Float } from '@react-three/drei';
import * as THREE from 'three';
import {
    Layout, Upload, Loader2, Send, Brain,
    Shield, ShoppingCart, Palette, Eye, Box,
    Maximize, RotateCcw, Layers, Zap, MessageSquare,
    CheckCircle2, AlertTriangle, Command, GitCompare,
    Sparkles, X, Check, ArrowRight, FileCode2,
    Wrench, SearchCode, Image, Gauge, Download, FileDown
} from 'lucide-react';
import { useBIMStore } from './hooks/useBIMStore';
import { BIMElement, BIMProjectState, CONTEXT_REFS, LintIssue, DiffEntry } from './services/api';

/* ========== 3D Renderers (Photorealistic PBR) ========== */
function BIMElementRenderer({ element, ghostStatus, realisticMode }: { element: BIMElement; ghostStatus?: 'added' | 'removed' | 'modified' | null; realisticMode?: boolean }) {
    const { position, rotation, dimensions, type } = element;
    const itemType = (element.metadata?.item_type || '').toLowerCase();

    const getMaterial = () => {
        if (ghostStatus === 'added') return { color: '#34d399', metalness: 0.1, roughness: 0.6, opacity: 0.85, transparent: true };
        if (ghostStatus === 'removed') return { color: '#f87171', metalness: 0.1, roughness: 0.6, opacity: 0.3, transparent: true };
        if (ghostStatus === 'modified') return { color: '#fbbf24', metalness: 0.1, roughness: 0.6, opacity: 0.85, transparent: true };

        if (realisticMode) {
            switch (type) {
                case 'wall': return { color: '#F0EDE8', metalness: 0.0, roughness: 0.95, opacity: 1, transparent: false };
                case 'door': return { color: '#5C4033', metalness: 0.15, roughness: 0.55, opacity: 1, transparent: false };
                case 'window': return { color: '#B8D8E8', metalness: 0.4, roughness: 0.1, opacity: 0.35, transparent: true };
                case 'furniture':
                    if (itemType.includes('sofa') || itemType.includes('chair') || itemType.includes('armchair'))
                        return { color: '#C4A882', metalness: 0.0, roughness: 0.85, opacity: 1, transparent: false };
                    if (itemType.includes('table') || itemType.includes('desk') || itemType.includes('dresser') || itemType.includes('stand'))
                        return { color: '#8B6F47', metalness: 0.08, roughness: 0.65, opacity: 1, transparent: false };
                    if (itemType.includes('lamp') || itemType.includes('light'))
                        return { color: '#F5E6CC', metalness: 0.6, roughness: 0.2, opacity: 0.9, transparent: true };
                    if (itemType.includes('bed'))
                        return { color: '#E8DDD4', metalness: 0.0, roughness: 0.9, opacity: 1, transparent: false };
                    return { color: '#D4C5B2', metalness: 0.05, roughness: 0.7, opacity: 1, transparent: false };
                default: return { color: '#888', metalness: 0.1, roughness: 0.5, opacity: 1, transparent: false };
            }
        }

        // Default (design mode) colors
        switch (type) {
            case 'wall': return { color: '#6d61ff', metalness: 0.3, roughness: 0.15, opacity: 1, transparent: false };
            case 'door': return { color: '#ff6b6b', metalness: 0.2, roughness: 0.4, opacity: 0.9, transparent: true };
            case 'window': return { color: '#4ecdc4', metalness: 0.5, roughness: 0.1, opacity: 0.4, transparent: true };
            case 'furniture': return { color: '#ffbd61', metalness: 0.05, roughness: 0.7, opacity: 1, transparent: false };
            default: return { color: '#888', metalness: 0.1, roughness: 0.5, opacity: 1, transparent: false };
        }
    };

    const mat = getMaterial();

    return (
        <group position={[position.x, position.y, position.z]} rotation={[rotation.x, rotation.y, rotation.z]}>
            <mesh castShadow receiveShadow>
                <boxGeometry args={[dimensions.x, dimensions.y, dimensions.z]} />
                <meshPhysicalMaterial
                    color={mat.color}
                    metalness={mat.metalness}
                    roughness={mat.roughness}
                    transparent={mat.transparent}
                    opacity={mat.opacity}
                    wireframe={ghostStatus === 'removed'}
                    clearcoat={realisticMode && type === 'furniture' ? 0.3 : 0}
                    clearcoatRoughness={0.4}
                    envMapIntensity={realisticMode ? 1.5 : 0.8}
                />
            </mesh>
        </group>
    );
}

/* ========== Floor Plane ========== */
function FloorPlane({ size = 30, realistic }: { size?: number; realistic?: boolean }) {
    return (
        <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[size / 4, -0.01, size / 4]}>
            <planeGeometry args={[size, size]} />
            <meshPhysicalMaterial
                color={realistic ? '#D4C1A1' : '#1a1a25'}
                metalness={0}
                roughness={realistic ? 0.75 : 0.9}
                opacity={realistic ? 1 : 0.4}
                transparent={!realistic}
            />
        </mesh>
    );
}

function BIMScene({ elements, ghostElements, realisticMode }: { elements: BIMElement[]; ghostElements?: { element: BIMElement; status: string }[]; realisticMode?: boolean }) {
    return (
        <>
            <PerspectiveCamera makeDefault position={[15, 15, 15]} fov={50} />
            <OrbitControls makeDefault minPolarAngle={0} maxPolarAngle={Math.PI / 1.75} enableDamping dampingFactor={0.05} />
            <ambientLight intensity={realisticMode ? 0.6 : 1.2} color={realisticMode ? '#FFF5E6' : '#ffffff'} />
            <spotLight position={[20, 25, 10]} angle={0.15} penumbra={1} intensity={realisticMode ? 3 : 2} castShadow shadow-mapSize={[2048, 2048]} color={realisticMode ? '#FFF0D4' : '#ffffff'} />
            {realisticMode && <>
                <spotLight position={[-10, 20, -5]} angle={0.3} penumbra={1} intensity={1} color="#E6F0FF" />
                <pointLight position={[5, 8, 5]} intensity={0.5} color="#FFE4B5" distance={15} decay={2} />
            </>}
            {!realisticMode && <Grid
                infiniteGrid fadeDistance={50} fadeStrength={5}
                cellSize={1} sectionSize={5} sectionThickness={1.5}
                sectionColor="#6d61ff" cellColor="#1a1a25"
            />}
            {realisticMode && <FloorPlane realistic />}
            {elements.map(el => (
                <BIMElementRenderer key={el.id} element={el} ghostStatus={null} realisticMode={realisticMode} />
            ))}
            {ghostElements?.map(g => (
                <BIMElementRenderer key={`ghost-${g.element.id}`} element={g.element} ghostStatus={g.status as any} />
            ))}
            <Environment preset={realisticMode ? 'apartment' : 'city'} />
            <ContactShadows position={[0, 0, 0]} opacity={realisticMode ? 0.6 : 0.3} scale={30} blur={realisticMode ? 1.5 : 2.5} far={realisticMode ? 3 : 1} />
        </>
    );
}

/* ========== Agent Helpers ========== */
function getAgentClass(agentName: string): string {
    const name = agentName.toLowerCase();
    if (name.includes('architect') || name.includes('vision')) return 'architect';
    if (name.includes('stylist')) return 'stylist';
    if (name.includes('compliance')) return 'compliance';
    if (name.includes('sourcing')) return 'sourcing';
    if (name.includes('memory') || name.includes('orchestrator')) return 'memory';
    if (name.includes('system')) return 'system';
    return '';
}

function getAgentIcon(agentName: string) {
    const name = agentName.toLowerCase();
    if (name.includes('architect') || name.includes('vision')) return <Eye size={12} />;
    if (name.includes('stylist')) return <Palette size={12} />;
    if (name.includes('compliance')) return <Shield size={12} />;
    if (name.includes('sourcing')) return <ShoppingCart size={12} />;
    if (name.includes('memory') || name.includes('orchestrator')) return <Brain size={12} />;
    return <Zap size={12} />;
}

/* ========== Command-K Modal ========== */
function CommandKModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (cmd: string) => void }) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [value, setValue] = useState('');

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') onClose();
        if (e.key === 'Enter' && value.trim()) {
            onSubmit(value);
            onClose();
        }
    };

    return (
        <div className="cmdk-overlay" onClick={onClose}>
            <div className="cmdk-modal" onClick={e => e.stopPropagation()}>
                <div className="cmdk-header">
                    <Command size={16} className="cmdk-icon" />
                    <span>VestaCode — Transform your spatial design</span>
                    <span className="cmdk-kbd">ESC</span>
                </div>
                <div className="cmdk-input-area">
                    <input
                        ref={inputRef}
                        className="cmdk-input"
                        placeholder="Describe your spatial edit... e.g. 'Convert living room to open-concept kitchen'"
                        value={value}
                        onChange={e => setValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                </div>
                <div className="cmdk-footer">
                    <span>
                        <ArrowRight size={12} /> Use <span className="cmdk-context-tag">@FloorPlan</span>
                        <span className="cmdk-context-tag">@Budget</span>
                        <span className="cmdk-context-tag">@Code</span> for context
                    </span>
                    <span>
                        <span className="cmdk-kbd">↵</span> to execute
                    </span>
                </div>
            </div>
        </div>
    );
}

/* ========== @ Reference Dropdown ========== */
function AtReferenceDropdown({ filter, onSelect }: { filter: string; onSelect: (label: string) => void }) {
    const filtered = CONTEXT_REFS.filter(r =>
        r.label.toLowerCase().includes(filter.toLowerCase()) ||
        r.type.toLowerCase().includes(filter.toLowerCase())
    );

    if (filtered.length === 0) return null;

    return (
        <div className="at-ref-dropdown">
            <div className="at-ref-header">Context References</div>
            {filtered.map(ref => (
                <button key={ref.type} className="at-ref-item" onClick={() => onSelect(ref.label)}>
                    <span className="ref-icon">{ref.icon}</span>
                    <div>
                        <div className="ref-label">{ref.label}</div>
                        <div className="ref-desc">{ref.description}</div>
                    </div>
                </button>
            ))}
        </div>
    );
}

/* ========== Design Lint Panel ========== */
function DesignLintPanel({ issues, onFixAll }: { issues: LintIssue[]; onFixAll: () => void }) {
    const errors = issues.filter(i => i.severity === 'error');
    const warnings = issues.filter(i => i.severity === 'warning');

    return (
        <div className="lint-panel">
            <div className="lint-panel-header">
                <div className="lint-title">
                    <SearchCode size={14} style={{ color: 'var(--accent)' }} />
                    <h3>Design Lint</h3>
                    {issues.length > 0 ? (
                        <span className={`lint-count ${errors.length > 0 ? 'error' : 'warning'}`}>
                            {issues.length}
                        </span>
                    ) : (
                        <span className="lint-count clean">✓</span>
                    )}
                </div>
                {issues.length > 0 && (
                    <button className="fix-all-btn" onClick={onFixAll}>
                        <Wrench size={11} /> Fix All
                    </button>
                )}
            </div>
            <div className="lint-list">
                {issues.length === 0 ? (
                    <div className="lint-empty">
                        <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
                        <span>No spatial errors detected</span>
                    </div>
                ) : (
                    issues.map(issue => (
                        <div key={issue.id} className="lint-item">
                            <div className={`lint-severity-dot ${issue.severity}`}></div>
                            <div className="lint-content">
                                <div className="lint-rule">{issue.rule_id}</div>
                                <div className="lint-message">{issue.message}</div>
                                {issue.fix_description && (
                                    <div className="lint-fix">💡 {issue.fix_description}</div>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

/* ========== Ghost Mode Diff Toolbar ========== */
function GhostModeToolbar({ diffs, onAcceptAll, onClose }: { diffs: DiffEntry[]; onAcceptAll: () => void; onClose: () => void }) {
    const added = diffs.filter(d => d.status === 'added').length;
    const removed = diffs.filter(d => d.status === 'removed').length;
    const modified = diffs.filter(d => d.status === 'modified').length;

    return (
        <div className="ghost-toolbar">
            <div className="ghost-label">
                <GitCompare size={14} className="diff-icon" />
                DIFF VIEW
            </div>
            <div className="diff-stats">
                {added > 0 && <span className="diff-stat added">+{added}</span>}
                {removed > 0 && <span className="diff-stat removed">−{removed}</span>}
                {modified > 0 && <span className="diff-stat modified">~{modified}</span>}
            </div>
            <div className="ghost-actions">
                <button className="ghost-accept-btn" onClick={onAcceptAll}>
                    <Check size={13} /> Accept All
                </button>
                <button className="ghost-reject-btn" onClick={onClose}>
                    <X size={13} /> Dismiss
                </button>
            </div>
        </div>
    );
}

/* ========== Spatial Score Panel ========== */
function SpatialScorePanel({ project }: { project: BIMProjectState | null }) {
    const spatialLog = project?.compliance_logs?.find((l: any) => l.agent === 'spatial_engine');
    if (!spatialLog) return null;

    const score = spatialLog.flow_score ?? 0;
    const scoreColor = score >= 80 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171';
    const circumference = 2 * Math.PI * 38;
    const offset = circumference - (score / 100) * circumference;

    return (
        <div className="glass-card">
            <div className="card-header">
                <Gauge size={14} className="card-icon" />
                <h3>Spatial Intelligence</h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <svg width="90" height="90" viewBox="0 0 90 90">
                    <circle cx="45" cy="45" r="38" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
                    <circle cx="45" cy="45" r="38" fill="none" stroke={scoreColor} strokeWidth="6"
                        strokeDasharray={circumference} strokeDashoffset={offset}
                        strokeLinecap="round" transform="rotate(-90 45 45)"
                        style={{ transition: 'stroke-dashoffset 1s ease' }}
                    />
                    <text x="45" y="42" textAnchor="middle" fill={scoreColor} fontSize="18" fontWeight="800" fontFamily="var(--font-mono)">{score}</text>
                    <text x="45" y="56" textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="8" fontWeight="600">/100</text>
                </svg>
                <div style={{ flex: 1 }}>
                    <div className="spatial-stat-row">
                        <span>Collisions</span>
                        <span className={spatialLog.collision_count > 0 ? 'stat-warn' : 'stat-ok'}>{spatialLog.collision_count}</span>
                    </div>
                    <div className="spatial-stat-row">
                        <span>Clearance</span>
                        <span className={spatialLog.clearance_violations > 0 ? 'stat-warn' : 'stat-ok'}>{spatialLog.clearance_violations}</span>
                    </div>
                    <div className="spatial-stat-row">
                        <span>Blocked Paths</span>
                        <span className={spatialLog.blocked_paths > 0 ? 'stat-critical' : 'stat-ok'}>{spatialLog.blocked_paths}</span>
                    </div>
                    <div className="spatial-stat-row">
                        <span>Density</span>
                        <span>{(spatialLog.density_ratio * 100).toFixed(0)}%</span>
                    </div>
                    {spatialLog.corrections_applied > 0 && (
                        <div className="spatial-stat-row" style={{ marginTop: 4 }}>
                            <span style={{ color: '#34d399' }}><Zap size={10} /> Auto-fixes</span>
                            <span style={{ color: '#34d399' }}>{spatialLog.corrections_applied}</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

/* ========== Client Review Modal ========== */
function ClientReviewModal({ project, onClose }: { project: BIMProjectState; onClose: () => void }) {
    const elements = project.elements || [];
    const walls = elements.filter(e => e.type === 'wall').length;
    const furniture = elements.filter(e => e.type === 'furniture');
    const spatialLog = project.compliance_logs?.find((l: any) => l.agent === 'spatial_engine');
    const complianceLog = project.compliance_logs?.find((l: any) => 'summary' in l && l.agent !== 'spatial_engine');

    return (
        <div className="review-modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
            <div className="review-modal">
                <button className="review-close" onClick={onClose}><X size={20} /></button>

                <div className="review-header">
                    <div className="review-badge">CLIENT REVIEW</div>
                    <h2>{project.name || 'Design Proposal'}</h2>
                    <p className="review-subtitle">Photorealistic preview of your approved design</p>
                </div>

                {/* 3D Realistic Preview */}
                <div className="review-viewport">
                    <Canvas shadows gl={{ preserveDrawingBuffer: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.2 } as any}>
                        <Suspense fallback={null}>
                            <BIMScene elements={elements} realisticMode />
                        </Suspense>
                    </Canvas>
                    <div className="review-viewport-label">
                        <Eye size={12} /> Realistic Material Preview
                    </div>
                </div>

                {/* Summary Stats */}
                <div className="review-stats-grid">
                    <div className="review-stat">
                        <div className="review-stat-val">{walls}</div>
                        <div className="review-stat-label">Structural Walls</div>
                    </div>
                    <div className="review-stat">
                        <div className="review-stat-val">{furniture.length}</div>
                        <div className="review-stat-label">Furniture Items</div>
                    </div>
                    <div className="review-stat">
                        <div className="review-stat-val" style={{ color: spatialLog ? (spatialLog.flow_score >= 80 ? '#34d399' : '#fbbf24') : '#888' }}>
                            {spatialLog?.flow_score ?? '—'}
                        </div>
                        <div className="review-stat-label">Flow Score</div>
                    </div>
                    <div className="review-stat">
                        <div className="review-stat-val">${project.budget_total?.toLocaleString() || '0'}</div>
                        <div className="review-stat-label">Est. Budget</div>
                    </div>
                </div>

                {/* Furniture List */}
                <div className="review-section">
                    <h4>Furniture Placement</h4>
                    <div className="review-furniture-list">
                        {furniture.map(f => (
                            <div key={f.id} className="review-furniture-item">
                                <span className="review-furn-name">{f.metadata?.item_type || 'Item'}</span>
                                <span className="review-furn-pos">
                                    ({f.position.x.toFixed(1)}, {f.position.z.toFixed(1)})
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Compliance */}
                {complianceLog && (
                    <div className="review-section">
                        <h4>Compliance Status</h4>
                        <div className={`review-compliance-badge ${complianceLog.is_compliant ? 'pass' : 'fail'}`}>
                            {complianceLog.is_compliant ? <><CheckCircle2 size={14} /> All Codes Passed</> : <><AlertTriangle size={14} /> Issues Detected</>}
                        </div>
                        <p className="review-compliance-summary">{complianceLog.summary}</p>
                    </div>
                )}

                {/* Style DNA */}
                <div className="review-section">
                    <h4>Design DNA</h4>
                    <div className="review-style-theme">{project.style_profile?.theme || 'Japandi Modern'}</div>
                    <div className="style-swatches" style={{ marginTop: 8 }}>
                        <div className="swatch" style={{ background: project.style_profile?.palette?.wall_color || '#F5F5F0' }} />
                        <div className="swatch" style={{ background: '#2d2d2d' }} />
                        <div className="swatch" style={{ background: '#c4a882' }} />
                        <div className="swatch" style={{ background: '#6d61ff' }} />
                        <div className="swatch" style={{ background: '#ffbd61' }} />
                    </div>
                </div>

                <div className="review-actions">
                    <button className="review-btn secondary" onClick={onClose}>Request Changes</button>
                    <button className="review-btn primary" onClick={onClose}>
                        <Check size={16} /> Approve Design
                    </button>
                </div>
            </div>
        </div>
    );
}

/* ========== Main App ========== */
function App() {
    const {
        project, previousProject, isProcessing, logs,
        lintIssues, diffEntries, ghostMode,
        uploadPlan, sendMessage,
        acceptAllDiffs, toggleGhostMode
    } = useBIMStore();

    const fileInputRef = useRef<HTMLInputElement>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);
    const chatInputRef = useRef<HTMLInputElement>(null);

    // Command-K state
    const [showCommandK, setShowCommandK] = useState(false);
    // @ reference state
    const [showAtRef, setShowAtRef] = useState(false);
    const [atFilter, setAtFilter] = useState('');
    // Client review & realistic mode
    const [showReview, setShowReview] = useState(false);
    const [realisticMode, setRealisticMode] = useState(false);

    // Auto-scroll chat
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Global keyboard shortcuts
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            // Cmd+K / Ctrl+K — Command Palette
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setShowCommandK(true);
            }
            // Escape — close modals
            if (e.key === 'Escape') {
                setShowCommandK(false);
                setShowAtRef(false);
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    // Handle chat input for @ references
    const handleChatInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        const lastAt = val.lastIndexOf('@');
        if (lastAt !== -1 && lastAt === val.length - 1) {
            setShowAtRef(true);
            setAtFilter('');
        } else if (lastAt !== -1 && val.substring(lastAt + 1).match(/^\w*$/)) {
            setShowAtRef(true);
            setAtFilter(val.substring(lastAt + 1));
        } else {
            setShowAtRef(false);
        }
    };

    const handleAtRefSelect = (label: string) => {
        if (chatInputRef.current) {
            const val = chatInputRef.current.value;
            const lastAt = val.lastIndexOf('@');
            chatInputRef.current.value = val.substring(0, lastAt) + label + ' ';
            chatInputRef.current.focus();
        }
        setShowAtRef(false);
    };

    const handleCommandKSubmit = (cmd: string) => {
        sendMessage(cmd);
    };

    const elements = project?.elements || [];
    const wallCount = elements.filter(e => e.type === 'wall').length;
    const furnitureCount = elements.filter(e => e.type === 'furniture').length;
    const lastCompliance = project?.compliance_logs?.[project.compliance_logs.length - 1];

    // Compute ghost mode elements for 3D overlay
    const ghostElements = ghostMode ? diffEntries.flatMap(d => {
        const items: { element: BIMElement; status: string }[] = [];
        if (d.status === 'removed' && d.old_element) items.push({ element: d.old_element, status: 'removed' });
        if (d.status === 'added' && d.new_element) items.push({ element: d.new_element, status: 'added' });
        if (d.status === 'modified') {
            if (d.old_element) items.push({ element: d.old_element, status: 'removed' });
            if (d.new_element) items.push({ element: d.new_element, status: 'modified' });
        }
        return items;
    }) : [];

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) uploadPlan(file);
    };

    return (
        <div className="studio-container">
            {/* ===== COMMAND-K MODAL ===== */}
            {showCommandK && (
                <CommandKModal
                    onClose={() => setShowCommandK(false)}
                    onSubmit={handleCommandKSubmit}
                />
            )}

            {/* ===== HEADER ===== */}
            <header>
                <div className="logo">
                    <div className="logo-icon"><Layers size={18} /></div>
                    <div className="logo-text">VESTA<span>CODE</span></div>
                </div>

                {project && (
                    <div className="header-center">
                        <span className="separator">/</span>
                        <span>{project.name || 'Untitled Project'}</span>
                    </div>
                )}

                {/* Shortcut Hints */}
                <div className="shortcut-hints">
                    <span className="shortcut-hint">
                        <kbd>⌘K</kbd> Edit
                    </span>
                    <span className="shortcut-hint">
                        <kbd>@</kbd> Context
                    </span>
                </div>

                <div className="header-right">
                    <div className={`status-pill ${isProcessing ? 'processing' : 'active'}`}>
                        <span className="pulse-dot"></span>
                        {isProcessing ? 'Agents Working' : 'AI Active'}
                    </div>
                </div>
            </header>

            {/* ===== CLIENT REVIEW MODAL ===== */}
            {showReview && project && (
                <ClientReviewModal
                    project={project}
                    onClose={() => setShowReview(false)}
                />
            )}

            {/* ===== LEFT SIDEBAR ===== */}
            <aside className="sidebar">
                {/* Project Overview */}
                <div className="glass-card">
                    <div className="card-header">
                        <Box size={14} className="card-icon" />
                        <h3>Project Overview</h3>
                        {/* New Export Button */}
                        {project && (
                            <button
                                className="icon-btn-sm"
                                title="Export to Revit (IFC)"
                                onClick={async () => {
                                    try {
                                        const res = await fetch('http://localhost:25678/project/export/ifc', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify(project)
                                        });
                                        if (res.ok) {
                                            const blob = await res.blob();
                                            const url = window.URL.createObjectURL(blob);
                                            const a = document.createElement('a');
                                            a.href = url;
                                            a.download = `vesta_export_${project!.project_id}.ifc`;
                                            a.click();
                                        } else {
                                            const txt = await res.text();
                                            alert("Export failed: " + txt);
                                        }
                                    } catch (e) {
                                        alert("Error exporting: " + e);
                                    }
                                }}
                            >
                                <FileDown size={14} />
                            </button>
                        )}
                    </div>
                    {project ? (
                        <>
                            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                                {project.name || 'New Project'}
                            </div>
                            <div className="project-stats">
                                <div className="stat-item">
                                    <div className="stat-value">{wallCount}</div>
                                    <div className="stat-label">Walls</div>
                                </div>
                                <div className="stat-item">
                                    <div className="stat-value">{furnitureCount}</div>
                                    <div className="stat-label">Furniture</div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                            Upload a floor plan or press <kbd style={{
                                padding: '1px 5px', borderRadius: 3, background: 'rgba(255,255,255,0.06)',
                                border: '1px solid rgba(255,255,255,0.08)', fontFamily: 'var(--font-mono)',
                                fontSize: '0.7rem'
                            }}>⌘K</kbd> to begin.
                        </p>
                    )}
                </div>

                {/* Memory Pulse */}
                <div className="glass-card">
                    <div className="card-header">
                        <Brain size={14} className="card-icon" />
                        <h3>Memory Pulse</h3>
                    </div>
                    <div className="memory-indicators">
                        <div className="memory-dot-group">
                            <div className="memory-dot working"></div>
                            <span className="memory-label">Working</span>
                        </div>
                        <div className="memory-dot-group">
                            <div className="memory-dot episodic"></div>
                            <span className="memory-label">Episodic</span>
                        </div>
                        <div className="memory-dot-group">
                            <div className="memory-dot semantic"></div>
                            <span className="memory-label">Semantic</span>
                        </div>
                    </div>
                </div>

                {/* Design Linting Panel */}
                <DesignLintPanel
                    issues={lintIssues}
                    onFixAll={() => sendMessage('Fix all spatial errors and reposition furniture to meet ergonomic and ADA standards.')}
                />

                {/* Compliance Status */}
                <div className="glass-card">
                    <div className="card-header">
                        <Shield size={14} className="card-icon" />
                        <h3>Compliance</h3>
                    </div>
                    {lastCompliance ? (
                        <div className="compliance-status">
                            <div className={`compliance-badge ${lastCompliance.is_compliant ? 'pass' : 'fail'}`}>
                                {lastCompliance.is_compliant
                                    ? <><CheckCircle2 size={14} /> All Clear</>
                                    : <><AlertTriangle size={14} /> Issues Found</>
                                }
                            </div>
                        </div>
                    ) : (
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Awaiting first audit...</p>
                    )}
                    {lastCompliance && (
                        <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: 8 }}>
                            {lastCompliance.summary}
                        </p>
                    )}
                </div>

                {/* Spatial Intelligence */}
                <SpatialScorePanel project={project} />

                {/* Style DNA */}
                <div className="glass-card">
                    <div className="card-header">
                        <Palette size={14} className="card-icon" />
                        <h3>Style DNA</h3>
                    </div>
                    <div className="style-swatches">
                        <div className="swatch" style={{ background: '#F5F5F0' }} />
                        <div className="swatch" style={{ background: '#2d2d2d' }} />
                        <div className="swatch" style={{ background: '#c4a882' }} />
                        <div className="swatch" style={{ background: '#6d61ff' }} />
                        <div className="swatch" style={{ background: '#ffbd61' }} />
                    </div>
                    <div className="style-theme-name">
                        {project?.style_profile?.theme || 'Japandi Modern'}
                    </div>
                </div>

                {/* Budget */}
                {project && project.budget_total > 0 && (
                    <div className="budget-bar">
                        <span className="budget-label">Est. Budget</span>
                        <span className="budget-value">${project.budget_total.toLocaleString()}</span>
                    </div>
                )}

                {/* Upload + Review Buttons */}
                <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} accept="image/*,.pdf" />
                <button className="upload-btn" onClick={() => fileInputRef.current?.click()} disabled={isProcessing}>
                    {isProcessing
                        ? <><Loader2 size={18} className="animate-spin" /> Processing...</>
                        : <><Upload size={18} /> Upload Floor Plan</>
                    }
                </button>
                {project && elements.length > 0 && (
                    <button className="review-trigger-btn" onClick={() => setShowReview(true)}>
                        <Eye size={16} /> Client Review
                    </button>
                )}
            </aside>

            {/* ===== CENTER VIEWPORT ===== */}
            <main className="viewport">
                <Canvas shadows gl={{ antialias: true, toneMapping: realisticMode ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping, toneMappingExposure: 1.1 } as any}>
                    <Suspense fallback={null}>
                        <BIMScene elements={ghostMode ? [] : elements} ghostElements={ghostMode ? ghostElements : undefined} realisticMode={realisticMode} />
                    </Suspense>
                </Canvas>

                {/* Viewport Toolbar */}
                <div className="viewport-toolbar">
                    <button className={`viewport-btn ${!realisticMode ? 'active' : ''}`} title="Design View" onClick={() => setRealisticMode(false)}><Maximize size={16} /></button>
                    <button className={`viewport-btn ${realisticMode ? 'active' : ''}`} title="Realistic View" onClick={() => setRealisticMode(true)}><Eye size={16} /></button>
                    <button className="viewport-btn" title="Reset View"><RotateCcw size={16} /></button>
                    <button className="viewport-btn" title="Layers"><Layers size={16} /></button>
                    <button
                        className={`viewport-btn ${ghostMode ? 'ghost-active' : ''}`}
                        title="Ghost Mode (Diff View)"
                        onClick={toggleGhostMode}
                    >
                        <GitCompare size={16} />
                    </button>
                    {project && elements.length > 0 && (
                        <button className="viewport-btn review-btn" title="Client Review" onClick={() => setShowReview(true)}>
                            <Image size={16} />
                        </button>
                    )}
                </div>

                {/* Empty State */}
                {elements.length === 0 && !isProcessing && (
                    <div className="viewport-empty">
                        <div className="viewport-empty-icon"><Layout size={28} /></div>
                        <h3>Your Canvas Awaits</h3>
                        <p>Upload a 2D floor plan or press <strong>⌘K</strong> to start designing with your AI team.</p>
                    </div>
                )}

                {/* Ghost Mode Diff Toolbar */}
                {ghostMode && diffEntries.length > 0 && (
                    <GhostModeToolbar
                        diffs={diffEntries}
                        onAcceptAll={acceptAllDiffs}
                        onClose={toggleGhostMode}
                    />
                )}
            </main>

            {/* ===== RIGHT SIDEBAR: COMMAND CENTER ===== */}
            <aside className="agent-console">
                <div className="console-header">
                    <MessageSquare size={18} className="console-icon" />
                    <h3>Command Center</h3>
                </div>

                <div className="chat-messages">
                    {logs.length === 0 ? (
                        <div className="chat-empty">
                            <div className="chat-empty-icon"><Sparkles size={22} /></div>
                            <h4>Your Design Team</h4>
                            <p>Upload a plan, press ⌘K, or type a command with @references to collaborate.</p>
                        </div>
                    ) : (
                        logs.map((log, i) => {
                            const isUser = log.agent === 'User';
                            const agentClass = isUser ? '' : getAgentClass(log.agent);
                            return (
                                <div key={i} className={`msg-bubble ${isUser ? 'user' : 'agent'} ${agentClass}`}>
                                    <div className="msg-agent-name">
                                        {!isUser && getAgentIcon(log.agent)}
                                        {log.agent}
                                    </div>
                                    <div className="msg-text">
                                        {log.message.split(/(@\w+)/g).map((part, idx) =>
                                            part.startsWith('@') ?
                                                <span key={idx} style={{ color: 'var(--accent)', fontWeight: 700 }}>{part}</span> :
                                                part
                                        )}
                                    </div>
                                </div>
                            );
                        })
                    )}
                    <div ref={chatEndRef} />
                </div>

                <div className="chat-input-area">
                    {/* @ Reference Dropdown */}
                    {showAtRef && (
                        <AtReferenceDropdown filter={atFilter} onSelect={handleAtRefSelect} />
                    )}
                    <form onSubmit={(e) => {
                        e.preventDefault();
                        const input = chatInputRef.current;
                        if (input && input.value.trim()) {
                            sendMessage(input.value);
                            input.value = '';
                            setShowAtRef(false);
                        }
                    }}>
                        <div className="chat-input-wrapper">
                            <input
                                ref={chatInputRef}
                                name="chatMessage"
                                className="chat-input"
                                placeholder="Talk to your design team... use @ for context"
                                autoComplete="off"
                                disabled={isProcessing}
                                onChange={handleChatInputChange}
                            />
                            <button type="submit" className="chat-send-btn" disabled={isProcessing}>
                                {isProcessing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                            </button>
                        </div>
                    </form>
                </div>
            </aside>
        </div>
    );
}

export default App;
