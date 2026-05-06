import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import pgp from "pg-promise";
import { z } from "zod";

const server = new McpServer({
    name: "Database PostgreSQL MCP",
    version: "1.0.0"
});

const connection = pgp()("postgres://postgres:123456@localhost:5432/app");

server.tool("execute_query", "Execute query on PostgreSQL", {
    query: z.string().describe("SQL SELECT query to execute")
}, async ({ query }) => {
    const output = await connection.query(query);
    return {
        content: [
            {
                type: "text",
                text: `Result ${JSON.stringify(output, undefined, 2)}`
            }
        ]
    }
});

const transport = new StdioServerTransport();
server.connect(transport);
