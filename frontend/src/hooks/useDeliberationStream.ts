import useWebSocket from 'react-use-websocket';
import { useState, useRef, useEffect } from 'react';
import throttle from 'lodash/throttle';

export const useDeliberationStream = (paperId: string) => {
    const encodedPaperId = paperId ? encodeURIComponent(paperId) : "";
    const wsUrl = paperId ? `${import.meta.env.VITE_API_WSS_URL || 'ws://localhost:8080'}/api/ws/${encodedPaperId}` : null;
    const [messages, setMessages] = useState<any[]>([]);
    const [systemAlerts, setSystemAlerts] = useState<any[]>([]);
    const [liveTokenBuffer, setLiveTokenBuffer] = useState<string>("");
    const [currentRoundNum, setCurrentRoundNum] = useState<number>(1);
    const lastSeqId = useRef<number>(0);
    const buffer = useRef<any[]>([]);
    const accumulatedTokens = useRef<string>("");

    // Throttled token buffer updater (50ms interval) to prevent browser rendering freeze
    const throttledUpdate = useRef(
        throttle((tokens: string) => {
            setLiveTokenBuffer(tokens);
        }, 50)
    ).current;

    const { lastMessage, readyState } = useWebSocket(wsUrl, {
        shouldReconnect: () => true,
        reconnectAttempts: 10,
        reconnectInterval: (attemptNumber) => Math.min(Math.pow(2, attemptNumber) * 1000, 10000),
        onOpen: () => {
            if (lastSeqId.current > 0 && encodedPaperId) {
                fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/deliberation/${encodedPaperId}/replay?since_seq=${lastSeqId.current}`)
                    .then(res => res.json())
                    .then(deltas => {
                        if (Array.isArray(deltas)) {
                            buffer.current = [...buffer.current, ...deltas];
                            setMessages([...buffer.current]);
                        }
                    })
                    .catch(err => console.error("Replay fetch failed:", err));
            }
        }
    });

    useEffect(() => {
        if (lastMessage !== null) {
            try {
                const data = JSON.parse(lastMessage.data);
                lastSeqId.current = data.seq_id;
                buffer.current.push(data);

                if (data.round_num) {
                    setCurrentRoundNum(data.round_num);
                }

                if (data.type === 'token') {
                    accumulatedTokens.current += data.content;
                    throttledUpdate(accumulatedTokens.current);
                } else if (data.type === 'round_complete' || data.type === 'approval_required') {
                    setMessages([...buffer.current]);
                    accumulatedTokens.current = "";
                    setLiveTokenBuffer("");
                } else if (data.type === 'system_alert' || data.type === 'deliberation_completed' || data.type === 'deliberation_failed' || data.type === 'deliberation_aborted' || data.type === 'round_approved') {
                    setSystemAlerts(prev => [...prev, data]);
                }
            } catch (err) {
                console.error("Error parsing WS message:", err);
            }
        }
    }, [lastMessage]);

    const dismissAlert = (seqId: number) => {
        setSystemAlerts(prev => prev.filter(alert => alert.seq_id !== seqId));
    };

    const latestMessage = messages[messages.length - 1];
    const isApprovalRequired = latestMessage?.type === 'approval_required';

    return { 
        messages, 
        liveTokenBuffer, 
        readyState, 
        isApprovalRequired,
        currentRoundNum: latestMessage?.round_num || currentRoundNum,
        systemAlerts,
        dismissAlert
    };
};
