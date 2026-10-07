export class Logger {
  private readonly prefix: string;
  private readonly level: string;

  constructor(prefix: string = 'MisakaNet', level: string = 'info') {
    this.prefix = prefix;
    this.level = level;
  }

  info(message: string, ...args: unknown[]) {
    this.log('info', message, ...args);
  }

  warn(message: string, ...args: unknown[]) {
    this.log('warn', message, ...args);
  }

  error(message: string, ...args: unknown[]) {
    this.log('error', message, ...args);
  }

  debug(message: string, ...args: unknown[]) {
    this.log('debug', message, ...args);
  }

  private log(level: string, message: string, ...args: unknown[]) {
    const timestamp = new Date().toISOString();
    const formattedArgs = args.map(arg => {
      if (typeof arg === 'object' && arg !== null) {
        return JSON.stringify(arg, null, 2);
      }
      return String(arg);
    });
    
    console.log(`[${timestamp}] [${level.toUpperCase()}] [${this.prefix}] ${message} ${formattedArgs.join(' ')}`);
  }
}
