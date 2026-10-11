/**
 * Converte o formato interno de mensagens para o formato compatível com Anthropic.
 * Implementa a normalização de ordem de blocos para evitar erros 400 em endpoints 
 * como o do DeepSeek, que exigem que blocos de texto venham antes de tool_use.
 */

export interface MessageBlock {
  type: 'text' | 'thinking' | 'redacted_thinking' | 'tool_use' | 'tool_result';
  text?: string;
  id?: string;
  input?: any;
  output?: any;
  [key: string]: any;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: MessageBlock[];
}

export function convertToAnthropicMessages(messages: Message[]): Message[] {
  return messages.map(msg => {
    if (msg.role !== 'assistant') {
      return { ...msg };
    }

    const blocks = [...msg.content];
    
    // Rank de prioridade para ordenação:
    // 0: thinking / redacted_thinking
    // 1: text
    // 2: tool_use
    // 3: outros (tool_result, etc)
    const getRank = (b: MessageBlock): number => {
      if (b.type === 'thinking' || b.type === 'redacted_thinking') return 0;
      if (b.type === 'text') return 1;
      if (b.type === 'tool_use') return 2;
      return 3;
    };

    const hasToolUse = blocks.some(b => b.type === 'tool_use');
    const hasInvalidOrder = blocks.some((b, i) => 
      b.type === 'tool_use' && blocks.slice(i + 1).some(x => x.type === 'text')
    );

    // Se houver tool_use e houver texto depois dele, reordenamos
    if (hasToolUse && hasInvalidOrder) {
      const sortedBlocks = blocks
        .map((b, i) => ({ block: b, rank: getRank(b), originalIndex: i }))
        .sort((a, b) => {
          if (a.rank !== b.rank) {
            return a.rank - b.rank;
          }
          // Mantém a ordem relativa dentro do mesmo grupo de rank
          return a.originalIndex - b.originalIndex;
        })
        .map(item => item.block);

      return { ...msg, content: sortedBlocks };
    }

    return { ...msg, content: blocks };
  });
}
