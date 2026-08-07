import useWebSocket from 'react-use-websocket';
import { useState, useRef, useEffect } from 'react';
import throttle from 'lodash/throttle';

export const useDeliberationStream = (paperId: string) => {
    // Falls back gracefully to localhost if environment variables are not injected
    const wsUrl = `${import.meta.env.VITE_API_WSS_URL || 'ws://localhost:8080'}/api/ws/${paperId}`;
    const [messages, setMessages] = useState<any[]>([]);
    const [systemAlerts, setSystemAlerts] = useState<any[]>([]);
    const [liveTokenBuffer, setLiveTokenBuffer] = useState<string>("");
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
            if (lastSeqId.current > 0) {
                fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/deliberation/${paperId}/replay?since_seq=${lastSeqId.current}`)
                    .then(res => res.json())
                    .then(deltas => {
                        buffer.current = [...buffer.current, ...deltas];
                        setMessages([...buffer.current]);
                    });
            }
        }
    });

    useEffect(() => {
        if (lastMessage !== null) {
            const data = JSON.parse(lastMessage.data);
            lastSeqId.current = data.seq_id;
            buffer.current.push(data);
            
            if (data.type === 'token') {
                accumulatedTokens.current += data.content;
                throttledUpdate(accumulatedTokens.current);
            } else if (data.type === 'round_complete' || data.type === 'approval_required') {
                setMessages([...buffer.current]);
                accumulatedTokens.current = "";
                setLiveTokenBuffer("");
            } else if (data.type === 'system_alert') {
                setSystemAlerts(prev => [...prev, data]);
            }
        }
    }, [lastMessage]);

    const dismissAlert = (seqId: number) => {
        setSystemAlerts(prev => prev.filter(alert => alert.seq_id !== seqId));
    };

    return { 
        messages, 
        liveTokenBuffer, 
        readyState, 
        isApprovalRequired: messages[messages.length - 1]?.type === 'approval_required',
        systemAlerts,
        dismissAlert
    };
};
