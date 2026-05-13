import { useState, useCallback, useEffect, useRef } from 'react';
import { ApiService, BIMProjectState, BIMElement, LintIssue, DiffEntry } from '../services/api';

export interface LogEntry {
    agent: string;
    message: string;
    timestamp: number;
}

const STEP_LABELS: Record<string, string> = {
    queued: '⏳ Queued…',
    vision: '🔍 Analyzing floor plan…',
    stylist: '🛋️ Designing interior…',
    spatial_validation: '📐 Validating geometry…',
    compliance: '🛡️ Checking regulations…',
    sourcing: '🛒 Finding products…',
    memory_refinery: '🧠 Learning preferences…',
    done: '✅ Complete',
    failed: '❌ Failed',
};

export function useBIMStore() {
    const [project, setProject] = useState<BIMProjectState | null>(null);
    const [previousProject, setPreviousProject] = useState<BIMProjectState | null>(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [pipelineStep, setPipelineStep] = useState<string>('');
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [lintIssues, setLintIssues] = useState<LintIssue[]>([]);
    const [diffEntries, setDiffEntries] = useState<DiffEntry[]>([]);
    const [ghostMode, setGhostMode] = useState(false);
    const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
    const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Auto-save: debounce 3s after any project change (skip demo project)
    useEffect(() => {
        if (!project || project.project_id === 'demo-japandi-penthouse') return;
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = setTimeout(() => {
            ApiService.saveProject(project).catch(() => {/* silent — non-blocking */});
        }, 3000);
        return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
    }, [project]);

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

        newState.elements.forEach(el => {
            if (!oldIds.has(el.id)) {
                entries.push({ element_id: el.id, status: 'added', new_element: el });
            }
        });

        oldState.elements.forEach(el => {
            if (!newIds.has(el.id)) {
                entries.push({ element_id: el.id, status: 'removed', old_element: el });
            }
        });

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

    // ---- Async upload with job polling ----
    const uploadPlan = async (file: File) => {
        setIsProcessing(true);
        setPipelineStep('queued');
        addLog('System', '🚀 Uploading floor plan — starting AI pipeline…');

        try {
            const { job_id } = await ApiService.uploadPlan(file);
            addLog('System', `Job ${job_id.slice(0, 8)}… created. Polling for status…`);

            // Poll every 2s
            const poll = async (): Promise<void> => {
                const job = await ApiService.pollJob(job_id);
                const label = STEP_LABELS[job.current_step] || job.current_step;
                setPipelineStep(label);

                if (job.status === 'completed' && job.result) {
                    setPreviousProject(project);
                    setProject(job.result.bim_state);
                    computeLintIssues(job.result.bim_state);
                    computeDiff(project, job.result.bim_state);
                    addLog('Architect', job.result.vision_notes || 'Wall geometry extracted. BIM state initialized.');
                    setIsProcessing(false);
                    setPipelineStep('');
                    return;
                }

                if (job.status === 'failed') {
                    addLog('System', `❌ Pipeline failed: ${job.error || 'Unknown error'}`);
                    setIsProcessing(false);
                    setPipelineStep('');
                    return;
                }

                // Still running — poll again
                await new Promise(r => setTimeout(r, 8000));
                return poll();
            };

            await poll();
        } catch (error) {
            console.error('Failed to upload plan:', error);
            addLog('System', '❌ Error: Failed to process floor plan.');
            setIsProcessing(false);
            setPipelineStep('');
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

    const loadDemo = async () => {
        setIsProcessing(true);
        addLog('System', '🏠 Loading Japandi Penthouse demo…');
        try {
            const result = await ApiService.loadDemo();
            setProject(result.bim_state);
            setPreviousProject(null);
            computeLintIssues(result.bim_state);
            computeDiff(null, result.bim_state);
            addLog('Architect', result.vision_notes);
        } catch (error) {
            addLog('System', '❌ Could not load demo. Is the backend running?');
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
            setProject(prev => prev ? { ...prev, elements: prev.elements.filter(e => e.id !== entryId) } : prev);
        } else if (entry.status === 'removed' && entry.old_element) {
            setProject(prev => prev ? { ...prev, elements: [...prev.elements, entry.old_element!] } : prev);
        } else if (entry.status === 'modified' && entry.old_element) {
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
        pipelineStep,
        logs,
        lintIssues,
        diffEntries,
        ghostMode,
        selectedElementId,
        uploadPlan,
        loadDemo,
        sendMessage,
        acceptDiffEntry,
        rejectDiffEntry,
        acceptAllDiffs,
        toggleGhostMode,
        setSelectedElementId
    };
}
