import axios from 'axios';

const API_BASE = '/api';

export interface Vector3 {
    x: number;
    y: number;
    z: number;
}

export interface BIMElement {
    id: string;
    type: string;
    position: Vector3;
    rotation: Vector3;
    dimensions: Vector3;
    model_url?: string;
    material_properties?: any;
    metadata: any;
}

export interface Room {
    id: string;
    name: string;
    polygon: [number, number][]; // List of [x, z] tuples
    elements: string[];
}

export interface BIMProjectState {
    project_id: string;
    name: string;
    elements: BIMElement[];
    rooms: Room[];
    style_profile: any;
    budget_total: number;
    compliance_logs: any[];
}

// Lint Issue from the Spatial Server
export interface LintIssue {
    id: string;
    severity: 'error' | 'warning' | 'info';
    element_id: string;
    rule_id: string;
    message: string;
    fix_description?: string;
}

// Diff Entry for Ghost Mode
export interface DiffEntry {
    element_id: string;
    status: 'added' | 'removed' | 'modified';
    old_element?: BIMElement;
    new_element?: BIMElement;
}

// @ Context Reference types
export type ContextRefType = 'FloorPlan' | 'Inspiration' | 'Budget' | 'Code' | 'Style';

export interface ContextRef {
    type: ContextRefType;
    label: string;
    icon: string;
    description: string;
}

export const CONTEXT_REFS: ContextRef[] = [
    { type: 'FloorPlan', label: '@FloorPlan', icon: '📐', description: 'Base dimensions & structural constraints' },
    { type: 'Inspiration', label: '@Inspiration', icon: '✨', description: 'Mood board or Pinterest reference' },
    { type: 'Budget', label: '@Budget', icon: '💰', description: 'Current project budget constraints' },
    { type: 'Code', label: '@Code', icon: '📋', description: 'ADA/IBC building regulations' },
    { type: 'Style', label: '@Style', icon: '🎨', description: 'Active style profile & preferences' },
];

export interface ProjectSummary {
    project_id: string;
    name: string;
    updated_at: string;
}

export interface JobResponse {
    job_id: string;
    project_id: string;
    kind: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    current_step: string;
    result: { project_id: string; bim_state: BIMProjectState; vision_notes: string } | null;
    error: string | null;
    created_at: string;
    completed_at: string | null;
}

export interface UploadResponse {
    job_id: string;
    project_id: string;
    status: string;
}

export const ApiService = {
    /** Start an async upload — returns a job_id for polling. */
    uploadPlan: async (file: File): Promise<UploadResponse> => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await axios.post(`${API_BASE}/project/upload-plan`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },

    /** Poll the status of a background pipeline job. */
    pollJob: async (jobId: string): Promise<JobResponse> => {
        const response = await axios.get(`${API_BASE}/project/job/${jobId}`);
        return response.data;
    },

    chatWithAgents: async (projectId: string, message: string, currentState: BIMProjectState): Promise<{ bim_state: BIMProjectState; agent_response: string }> => {
        const response = await axios.post(`${API_BASE}/project/chat`, {
            project_id: projectId,
            message,
            current_state: currentState,
        });
        return response.data;
    },

    // Persistence
    saveProject: async (project: BIMProjectState): Promise<{ status: string; project_id: string }> => {
        const response = await axios.post(`${API_BASE}/project/save`, project);
        return response.data;
    },

    loadProject: async (projectId: string): Promise<{ bim_state: BIMProjectState }> => {
        const response = await axios.get(`${API_BASE}/project/${projectId}`);
        return response.data;
    },

    listProjects: async (): Promise<{ projects: ProjectSummary[] }> => {
        const response = await axios.get(`${API_BASE}/projects`);
        return response.data;
    },

    deleteProject: async (projectId: string): Promise<void> => {
        await axios.delete(`${API_BASE}/project/${projectId}`);
    },

    // Demo
    loadDemo: async (): Promise<{ project_id: string; bim_state: BIMProjectState; vision_notes: string }> => {
        const response = await axios.get(`${API_BASE}/project/demo/load`);
        return response.data;
    },

    // Export
    exportIfc: async (project: BIMProjectState): Promise<Blob> => {
        const response = await axios.post(`${API_BASE}/project/export/ifc`, project, {
            responseType: 'blob'
        });
        return response.data;
    },

    exportDxf: async (project: BIMProjectState): Promise<Blob> => {
        const response = await axios.post(`${API_BASE}/project/export/dxf`, project, {
            responseType: 'blob'
        });
        return response.data;
    },
};
