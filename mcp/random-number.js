import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new McpServer({
    name: "Random Number MCP",
    version: "1.0.0"
});

server.tool("get_random_number", "Generate a random number", {}, async () => {
    const output = Math.floor(Math.random() * 1000);
    return {
        content: [
            {
                type: "text",
                text: `Random number ${output}`
            }
        ]
    }
});

const transport = new StdioServerTransport();
server.connect(transport);