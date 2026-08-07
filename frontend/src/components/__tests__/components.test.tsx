import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DataPanel } from '../DataPanel';
import { TokenStream } from '../TokenStream';
import { ApprovalControls } from '../ApprovalControls';

describe('DataPanel Component', () => {
  it('renders score, verdict and paper path correctly', () => {
    render(
      <DataPanel
        aggregateScore={4.5}
        verdict="Strong Accept"
        paperPath="tests/fixtures/test_paper.txt"
        abstractText="This is a test abstract."
      />
    );

    expect(screen.getByText('4.50')).toBeInTheDocument();
    expect(screen.getByText('/5.0')).toBeInTheDocument();
    expect(screen.getByText('Strong Accept')).toBeInTheDocument();
    expect(screen.getByText('tests/fixtures/test_paper.txt')).toBeInTheDocument();
    expect(screen.getByText('This is a test abstract.')).toBeInTheDocument();
  });
});

describe('TokenStream Component', () => {
  it('renders token buffer if present', () => {
    render(<TokenStream tokenBuffer="thinking out loud..." />);
    expect(screen.getByText('thinking out loud...')).toBeInTheDocument();
  });

  it('renders nothing if token buffer is empty', () => {
    const { container } = render(<TokenStream tokenBuffer="" />);
    expect(container.firstChild).toBeNull();
  });
});

describe('ApprovalControls Component', () => {
  it('renders nothing when approval is not required', () => {
    const { container } = render(
      <ApprovalControls
        isApprovalRequired={false}
        roundNum={1}
        onApprove={() => {}}
        onAbort={() => {}}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('calls handlers when approve or abort buttons are clicked', () => {
    const onApprove = vi.fn();
    const onAbort = vi.fn();

    render(
      <ApprovalControls
        isApprovalRequired={true}
        roundNum={2}
        onApprove={onApprove}
        onAbort={onAbort}
      />
    );

    expect(screen.getByText('Approve Round 2 and Continue')).toBeInTheDocument();
    expect(screen.getByText('Abort Deliberation')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('approve-btn'));
    expect(onApprove).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId('abort-btn'));
    expect(onAbort).toHaveBeenCalledTimes(1);
  });
});
