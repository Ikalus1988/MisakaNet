# MisakaNet Integration for Cursor

## Overview

This integration allows Cursor to search MisakaNet for relevant coding lessons, providing auto-suggestions during debugging.

## Prerequisites

- Python 3.x
- Flask
- Requests

## Installation

1. **Clone the repository:**

   ```sh
   git clone https://github.com/your-repo.git
   cd your-repo
   ```

2. **Install dependencies:**

   ```sh
   pip install flask requests
   ```

3. **Start the MCP server:**

   ```sh
   python server.py
   ```

4. **Configure Cursor:**

   - Place the `.cursorrules` file in the root of your project.
   - Ensure Cursor is configured to use the `.cursorrules` file.

5. **Auto-Suggest Functionality:**

   - Use the `auto_suggest.py` script to get auto-suggestions during debugging.

## Usage

- Run the `auto_suggest.py` script with a query to get relevant lesson suggestions.

  ```sh
  python auto_suggest.py "python"
  ```

- The script will output suggested lessons based on the query.

## Troubleshooting

- If the MCP server is not responding, ensure it is running and accessible at `http://localhost:8080`.
- Check the network connection and firewall settings if you encounter issues.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License.