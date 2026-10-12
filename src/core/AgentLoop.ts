import { AgentContext, AgentStatus, incrementRetryBudget, resetRetryBudget } from '../types/AgentState';
import { executeTool } from '../tools/executor';
import { logger } from '../utils/logger';

export async function runAgentLoop(context: AgentContext) {
  while (context.status !== AgentStatus.IDLE && context.status !== AgentStatus.PARALYZED) {
    
    // 1. Verificar se estamos paralisados
    if (context.status === AgentStatus.PARALYZED) {
      logger.warn('Agent is paralyzed. Waiting for human intervention or manual reset.');
      await new Promise(resolve => setTimeout(resolve, 5000)); // Polling leve
      continue;
    }

    try {
      // 2. Gerar próximo passo (LLM decide qual ferramenta usar)
      const nextStep = await generateNextStep(context);
      
      if (!nextStep || !nextStep.toolName) {
        context.status = AgentStatus.IDLE;
        break;
      }

      // 3. Verificar orçamento de retry ANTES de executar
      const { budget, shouldStop } = incrementRetryBudget(
        context, 
        nextStep.toolName, 
        false // Ainda não sabemos se falhou, mas vamos preparar o contador
      );
      
      // Nota: A lógica real de "deveria parar" deve ser aplicada após a execução ou durante a geração se o LLM tentar a mesma coisa repetidamente.
      // Para simplificar, vamos aplicar a verificação estrita após a falha no bloco catch, 
      // mas aqui verificamos se o orçamento já estava estourado de iterações anteriores.
      if (budget.currentAttemptCount > budget.maxAttemptsPerGoal && budget.consecutiveFailuresSameRootCause > 0) {
         logger.error(`Retry budget exceeded (${budget.currentAttemptCount} attempts). Stopping to prevent runaway loop.`);
         context.status = AgentStatus.PARALYZED;
         context.retryBudget = budget;
         break;
      }

      context.status = AgentStatus.EXECUTING;
      
      // 4. Executar a ferramenta
      const result = await executeTool(nextStep.toolName, nextStep.args);
      
      // 5. Sucesso: Resetar orçamento
      context.retryBudget = resetRetryBudget(context).retryBudget;
      context.status = AgentStatus.THINKING;
      
      // Atualizar contexto com resultado para próxima iteração
      updateContextWithResult(context, result);

    } catch (error) {
      logger.error(`Tool execution failed: ${error.message}`);
      
      // Incrementar contagem de falha
      const { budget, shouldStop } = incrementRetryBudget(
        context, 
        context.lastFailedToolName || 'unknown', 
        true
      );
      
      context.retryBudget = budget;

      // Se o orçamento foi estourado, entrar em estado de paralisação
      if (shouldStop || budget.currentAttemptCount >= budget.maxAttemptsPerGoal) {
        logger.critical('Max retry attempts reached with consistent failure pattern. Entering PARALYZED state.');
        context.status = AgentStatus.PARALYZED;
        
        // Gerar mensagem de erro clara para o usuário/human-in-the-loop
        const emergencyMessage = `I am unable to proceed. I have tried ${budget.currentAttemptCount} different approaches and all failed due to [${budget.lastFailedToolName || 'structural'}] issues. Please check the configuration or intervene manually.`;
        addMessageToHistory(context, { role: 'assistant', content: emergencyMessage });
        
        break;
      } else {
        // Falha temporária, continuar tentando (mas com orçamento atualizado)
        context.status = AgentStatus.THINKING;
      }
    }
  }
}

// Stub functions for context
function generateNextStep(ctx: any) { throw new Error('Not implemented'); }
function updateContextWithResult(ctx: any, res: any) { ctx.history.push(res); }
function addMessageToHistory(ctx: any, msg: any) { ctx.history.push(msg); }
