import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useDeliberationStream } from './useDeliberationStream';

// Mock react-use-websocket
const mockSendJsonMessage = vi.fn();
let mockLastMessage: any = null;
let mockReadyState = 1; // Open

vi.mock('react-use-websocket', () => {
  return {
    default: () => ({
      sendJsonMessage: mockSendJsonMessage,
      lastMessage: mockLastMessage,
      readyState: mockReadyState,
    }),
  };
});

describe('useDeliberationStream Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLastMessage = null;
    mockReadyState = 1;
  });

  it('should initialize with empty state values', () => {
    const { result } = renderHook(() => useDeliberationStream('123'));
    expect(result.current.messages).toEqual([]);
    expect(result.current.liveTokenBuffer).toBe("");
    expect(result.current.isApprovalRequired).toBe(false);
    expect(result.current.systemAlerts).toEqual([]);
    expect(typeof result.current.dismissAlert).toBe('function');
  });
});
