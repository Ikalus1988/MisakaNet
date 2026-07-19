const lessons = [
    'Lesson 1: Introduction to JavaScript',
    'Lesson 2: Advanced JavaScript Concepts',
    'Lesson 3: Introduction to TypeScript',
    'Lesson 4: Web Development with React',
    'Lesson 5: Node.js Basics',
    // Add more lessons as needed
];

export function searchLessons(term: string): string[] {
    return lessons.filter(lesson => lesson.toLowerCase().includes(term.toLowerCase()));
}
