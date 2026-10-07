import axios from 'axios';
import { JSDOM } from 'jsdom';
import type { Tool } from './types.js';

interface WebFetchOptions {
  url: string;
  timeout?: number;
  retries?: number;
  followRedirects?: boolean;
}

interface WebFetchResult {
  success: boolean;
  content: string;
  contentType: string;
  status: number;
  url: string;
  error?: string;
}

const DEFAULT_TIMEOUT = 10000; // 10 seconds
const MAX_RETRIES = 3;
const USER_AGENT = 'MisakaNet-Agent/1.0 (compatible; +https://github.com/Ikalus1988/MisakaNet)';

class WebFetchTool implements Tool {
  readonly name = 'web_fetch';
  readonly description = 'Fetch content from a URL and return the text content';
  readonly parameters = {
    type: 'object',
    properties: {
      url: {
        type: 'string',
        description: 'The URL to fetch content from'
      },
      timeout: {
        type: 'number',
        description: 'Request timeout in milliseconds (default: 10000)'
      }
    },
    required: ['url']
  };

  async execute(options: WebFetchOptions): Promise<WebFetchResult> {
    const {
      url,
      timeout = DEFAULT_TIMEOUT,
      retries = MAX_RETRIES,
      followRedirects = true
    } = options;

    // Validate URL format
    try {
      new URL(url);
    } catch {
      return {
        success: false,
        content: '',
        contentType: 'text/plain',
        status: 0,
        url,
        error: 'Invalid URL format'
      };
    }

    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const response = await this.fetchWithTimeout(url, timeout, followRedirects);
        
        if (!response.ok) {
          if (attempt < retries && this.isRetryableError(response.status)) {
            await this.delay(Math.pow(2, attempt) * 1000);
            continue;
          }
          return {
            success: false,
            content: '',
            contentType: 'text/plain',
            status: response.status,
            url,
            error: `HTTP ${response.status}: ${response.statusText}`
          };
        }

        const content = await this.extractContent(response);
        
        return {
          success: true,
          content,
          contentType: response.headers.get('content-type') || 'text/plain',
          status: response.status,
          url: response.url
        };
      } catch (error) {
        lastError = error as Error;
        
        if (attempt < retries && this.isRetryableError(lastError)) {
          await this.delay(Math.pow(2, attempt) * 1000);
          continue;
        }
      }
    }

    return {
      success: false,
      content: '',
      contentType: 'text/plain',
      status: 0,
      url,
      error: lastError?.message || 'Web fetch failed after retries'
    };
  }

  private async fetchWithTimeout(
    url: string,
    timeout: number,
    followRedirects: boolean
  ): Promise<Response> {
    try {
      // Use Node.js built-in fetch with proper options
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'User-Agent': USER_AGENT,
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.5',
          'Accept-Encoding': 'identity',
          'Connection': 'keep-alive',
          'Cache-Control': 'no-cache'
        },
        signal: controller.signal,
        redirect: followRedirects ? 'follow' : 'manual',
        // Increase max redirects to handle GitHub redirects
        maxRedirects: 10
      });

      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      // Handle different error types
      if (error && typeof error === 'object' && 'name' in error) {
        if (error.name === 'AbortError') {
          throw new Error(`Request timed out after ${timeout}ms`);
        }
        if (error.name === 'TypeError' && error.message?.includes('fetch failed')) {
          // This often happens with HTTPS certificate issues or network problems
          throw new Error(`Network error: Failed to fetch ${url}. Check if the URL is accessible.`);
        }
      }
      throw error;
    }
  }

  private async extractContent(response: Response): Promise<string> {
    const contentType = response.headers.get('content-type') || '';
    
    // Handle different content types
    if (contentType.includes('text/html') || contentType.includes('application/xhtml+xml')) {
      return this.extractHtmlContent(response);
    } else if (contentType.includes('text/plain')) {
      return this.extractPlainText(response);
    } else if (contentType.includes('application/json')) {
      const json = await response.json();
      return JSON.stringify(json, null, 2);
    } else if (contentType.includes('markdown') || contentType.includes('text/markdown')) {
      return await response.text();
    } else {
      // Try to get text content for unknown types
      return this.extractPlainText(response);
    }
  }

  private async extractHtmlContent(response: Response): Promise<string> {
    const html = await response.text();
    
    try {
      const dom = new JSDOM(html);
      const document = dom.window.document;
      
      // Remove script and style elements
      const scripts = document.querySelectorAll('script, style, nav, footer, header');
      scripts.forEach(script => script.remove());
      
      // Get text content
      const body = document.body?.textContent || '';
      
      // Clean up whitespace
      return body
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .join('\n')
        .replace(/\s+/g, ' ')
        .trim();
    } catch {
      // Fallback to plain text extraction
      return this.extractPlainText(response);
    }
  }

  private async extractPlainText(response: Response): Promise<string> {
    try {
      return await response.text();
    } catch {
      return '';
    }
  }

  private isRetryableError(error: Error | undefined): boolean {
    if (!error) return false;
    
    const errorMessage = error.message.toLowerCase();
    
    // Retry on network errors, timeouts, and server errors
    const retryablePatterns = [
      'timeout',
      'abort',
      'econnreset',
      'econnrefused',
      'enotfound',
      'etagain',
      'network',
      'fetch failed'
    ];
    
    return retryablePatterns.some(pattern => errorMessage.includes(pattern));
  }

  private isRetryableError(status: number): boolean {
    // Retry on 429 (Too Many Requests) and 5xx errors
    return status === 429 || (status >= 500 && status < 600);
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export const webFetchTool = new WebFetchTool();
