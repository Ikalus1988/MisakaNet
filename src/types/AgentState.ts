import { ToolCall } from './tools';

export enum AgentStatus {
  IDLE = 'idle',
  THINKING = 'thinking',
  EXECUTING = 'executing',
  WAITING_FOR_APPROVAL = 'waiting_for_approval',
  ERROR = 'error',
  // Novo estado: Paralisado devido a falha estrutural ou orçamento esgotado
  PARALYZED = 'paralyzed' 
}

export interface RetryBudget {
  maxAttemptsPerGoal: number;
  currentAttemptCount: number;
  lastFailedToolName?: string;
  consecutiveFailuresSameRootCause: number;
}

export interface AgentContext {
  status: AgentStatus;
  retryBudget: RetryBudget;
  // ... outros campos existentes
}

// Função auxiliar para resetar o orçamento quando o contexto muda significativamente
export const resetRetryBudget = (context: Partial<AgentContext>): Partial<AgentContext> => ({
  retryBudget: {
    maxAttemptsPerGoal: 3, // Limite seguro definido na issue
    currentAttemptCount: 0,
    lastFailedToolName: undefined,
    consecutiveFailuresSameRootCause: 0,
  },
});

// Função para incrementar e verificar o orçamento
export const incrementRetryBudget = (
  context: AgentContext,
  toolName: string,
  isFailure: boolean
): { budget: RetryBudget; shouldStop: boolean } => {
  if (!isFailure) {
    return { budget: context.retryBudget, shouldStop: false };
  }

  const newCount = context.retryBudget.currentAttemptCount + 1;
  const sameRootCause = context.retryBudget.lastFailedToolName === toolName 
    ? context.retryBudget.consecutiveFailuresSameRootCause + 1 
    : 1;

  const updatedBudget = {
    ...context.retryBudget,
    currentAttemptCount: newCount,
    lastFailedToolName: toolName,
    consecutiveFailuresSameRootCause: sameRootCause,
  };

  // Se tentarmos mais de 3 vezes com falha, ou se houver falhas consecutivas da mesma causa raiz
  const shouldStop = newCount >= updatedBudget.maxAttemptsPerGoal || 
                     sameRootCause >= 2; // 2 falhas seguidas do mesmo tipo já indicam problema estrutural

  return { budget: updatedBudget, shouldStop };
};
