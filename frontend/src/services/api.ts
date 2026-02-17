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
    metadata: any;
}

export interface BIMProjectState {
    project_id: string;
    name: string;
    elements: BIMElement[];
    rooms: any[];
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

export const ApiService = {
    uploadPlan: async (file: File): Promise<{ project_id: string; bim_state: BIMProjectState; vision_notes: string }> => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await axios.post(`${API_BASE}/project/upload-plan`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        return response.data;
    },

    chatWithAgents: async (projectId: string, message: string, currentState: BIMProjectState): Promise<{ bim_state: BIMProjectState; agent_response: string }> => {
        const response = await axios.post(`${API_BASE}/project/chat`, {
            project_id: projectId,
            message,
            current_state: currentState
        });

        return response.data;
    },
};
