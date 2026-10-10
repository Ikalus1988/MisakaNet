import React from 'react';

/**
 * Componente MissingLesson
 * Exibido quando uma lição solicitada não é encontrada ou está indisponível.
 * Resolve a issue #3136 - missing_lesson
 */
const MissingLesson: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] p-4 text-center">
      <h2 className="text-2xl font-bold mb-2 text-gray-800 dark:text-white">
        Lição Não Encontrada
      </h2>
      <p className="text-gray-600 dark:text-gray-300 mb-4">
        A lição que você está procurando parece estar ausente ou indisponível no momento.
      </p>
      <button
        onClick={() => window.history.back()}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
      >
        Voltar
      </button>
    </div>
  );
};

export default MissingLesson;
