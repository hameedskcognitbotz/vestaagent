import { useState, useCallback } from 'react';
import { ApiService, BIMProjectState, BIMElement, LintIssue, DiffEntry } from '../services/api';

export interface LogEntry {
    agent: string;
    message: string;
    timestamp: number;
}

export function useBIMStore() {
    const [project, setProject] = useState<BIMProjectState | null>(null);
    const [previousProject, setPreviousProject] = useState<BIMProjectState | null>(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [lintIssues, setLintIssues] = useState<LintIssue[]>([]);
    const [diffEntries, setDiffEntries] = useState<DiffEntry[]>([]);
    const [ghostMode, setGhostMode] = useState(false);
    const [selectedElementId, setSelectedElementId] = useState<string | null>(null);

    const addLog = useCallback((agent: string, message: string) => {
        setLogs(prev => [...prev, { agent, message, timestamp: Date.now() }]);
    }, []);

    // Compute lint issues from compliance logs
    const computeLintIssues = useCallback((state: BIMProjectState) => {
        const issues: LintIssue[] = [];
        const lastCompliance = state.compliance_logs?.[state.compliance_logs.length - 1];

        if (lastCompliance && !lastCompliance.is_compliant && lastCompliance.violations) {
            lastCompliance.violations.forEach((v: any, i: number) => {
                issues.push({
                    id: `lint-${i}`,
                    severity: v.severity === 'critical' ? 'error' : 'warning',
                    element_id: v.element_id || '',
                    rule_id: v.rule_id || 'SPATIAL',
                    message: v.description || v.message || 'Spatial violation detected.',
                    fix_description: v.remediation_advice || v.fix
                });
            });
        }

        // Add common spatial checks client-side
        state.elements.forEach(el => {
            if (el.type === 'furniture') {
                // Check for overlapping furniture
                state.elements.forEach(other => {
                    if (other.id !== el.id && other.type === 'furniture') {
                        const dx = Math.abs(el.position.x - other.position.x);
                        const dz = Math.abs(el.position.z - other.position.z);
                        const minDist = (el.dimensions.x + other.dimensions.x) / 2;
                        if (dx < minDist * 0.5 && dz < minDist * 0.5) {
                            issues.push({
                                id: `overlap-${el.id}-${other.id}`,
                                severity: 'warning',
                                element_id: el.id,
                                rule_id: 'ERGO-001',
                                message: `Furniture overlap: "${el.metadata?.item_type || 'item'}" too close to "${other.metadata?.item_type || 'item'}".`,
                                fix_description: 'Increase spacing to at least 0.8m between items.'
                            });
                        }
                    }
                });
            }
        });

        setLintIssues(issues);
    }, []);

    // Compute diff between previous and current state
    const computeDiff = useCallback((oldState: BIMProjectState | null, newState: BIMProjectState) => {
        if (!oldState) {
            setDiffEntries(newState.elements.map(el => ({
                element_id: el.id,
                status: 'added' as const,
                new_element: el
            })));
            return;
        }

        const entries: DiffEntry[] = [];
        const oldIds = new Set(oldState.elements.map(e => e.id));
        const newIds = new Set(newState.elements.map(e => e.id));

        // Added elements
        newState.elements.forEach(el => {
            if (!oldIds.has(el.id)) {
                entries.push({ element_id: el.id, status: 'added', new_element: el });
            }
        });

        // Removed elements
        oldState.elements.forEach(el => {
            if (!newIds.has(el.id)) {
                entries.push({ element_id: el.id, status: 'removed', old_element: el });
            }
        });

        // Modified elements
        newState.elements.forEach(nel => {
            const oel = oldState.elements.find(e => e.id === nel.id);
            if (oel) {
                const posChanged = oel.position.x !== nel.position.x || oel.position.y !== nel.position.y || oel.position.z !== nel.position.z;
                const dimChanged = oel.dimensions.x !== nel.dimensions.x || oel.dimensions.y !== nel.dimensions.y || oel.dimensions.z !== nel.dimensions.z;
                if (posChanged || dimChanged) {
                    entries.push({ element_id: nel.id, status: 'modified', old_element: oel, new_element: nel });
                }
            }
        });

        setDiffEntries(entries);
    }, []);

    const uploadPlan = async (file: File) => {
        setIsProcessing(true);
        addLog('System', '🚀 Uploading floor plan to Vision Agent...');

        try {
            const result = await ApiService.uploadPlan(file);
            setPreviousProject(project);
            setProject(result.bim_state);
            computeLintIssues(result.bim_state);
            computeDiff(project, result.bim_state);
            addLog('Architect', result.vision_notes || 'Wall geometry extracted. BIM state initialized.');
        } catch (error) {
            console.error('Failed to upload plan:', error);
            addLog('System', '❌ Error: Failed to process floor plan.');
        } finally {
            setIsProcessing(false);
        }
    };

    const sendMessage = async (message: string) => {
        if (!project) return;

        addLog('User', message);
        setIsProcessing(true);

        try {
            const result = await ApiService.chatWithAgents(project.project_id, message, project);
            setPreviousProject(project);
            setProject(result.bim_state);
            computeLintIssues(result.bim_state);
            computeDiff(project, result.bim_state);

            // Parse multi-agent responses
            const response = result.agent_response;
            if (response.includes('[Stylist]')) addLog('Stylist', response.replace('[Stylist]: ', ''));
            else if (response.includes('[Compliance]')) addLog('Compliance', response.replace('[Compliance]: ', ''));
            else if (response.includes('[Sourcing]')) addLog('Sourcing', response.replace('[Sourcing]: ', ''));
            else if (response.includes('[Architect]')) addLog('Architect', response.replace('[Architect]: ', ''));
            else addLog('Orchestrator', response);
        } catch (error) {
            console.error('Chat failed:', error);
            addLog('System', '⚠️ Agents are currently unavailable. Check backend connection.');
        } finally {
            setIsProcessing(false);
        }
    };

    // Accept a single diff change
    const acceptDiffEntry = useCallback((entryId: string) => {
        setDiffEntries(prev => prev.filter(e => e.element_id !== entryId));
    }, []);

    // Reject a single diff change (revert to old)
    const rejectDiffEntry = useCallback((entryId: string) => {
        if (!project || !previousProject) return;
        const entry = diffEntries.find(e => e.element_id === entryId);
        if (!entry) return;

        if (entry.status === 'added') {
            // Remove the added element
            setProject(prev => prev ? { ...prev, elements: prev.elements.filter(e => e.id !== entryId) } : prev);
        } else if (entry.status === 'removed' && entry.old_element) {
            // Restore the removed element
            setProject(prev => prev ? { ...prev, elements: [...prev.elements, entry.old_element!] } : prev);
        } else if (entry.status === 'modified' && entry.old_element) {
            // Revert to old version
            setProject(prev => prev ? {
                ...prev,
                elements: prev.elements.map(e => e.id === entryId ? entry.old_element! : e)
            } : prev);
        }
        setDiffEntries(prev => prev.filter(e => e.element_id !== entryId));
    }, [project, previousProject, diffEntries]);

    const acceptAllDiffs = useCallback(() => {
        setDiffEntries([]);
        setGhostMode(false);
    }, []);

    const toggleGhostMode = useCallback(() => {
        setGhostMode(prev => !prev);
    }, []);

    return {
        project,
        previousProject,
        isProcessing,
        logs,
        lintIssues,
        diffEntries,
        ghostMode,
        selectedElementId,
        uploadPlan,
        sendMessage,
        acceptDiffEntry,
        rejectDiffEntry,
        acceptAllDiffs,
        toggleGhostMode,
        setSelectedElementId
    };
}
