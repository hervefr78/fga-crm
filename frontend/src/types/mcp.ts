// =============================================================================
// FGA CRM - Types : MCP Usage (conso API par tool, cout €)
// =============================================================================

export interface McpUsageTotal {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cache_read: number;
  cache_write: number;
  cost_eur: number;
}

export interface ToolUsageSummary {
  tool_name: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_eur: number;
}

export interface McpUsageSummary {
  date_from: string;
  date_to: string;
  total: McpUsageTotal;
  by_tool: ToolUsageSummary[];
}

export interface McpUsageByToolRow {
  day: string;
  model: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_eur: number;
}

export interface McpUsageByTool {
  tool_name: string;
  date_from: string;
  date_to: string;
  rows: McpUsageByToolRow[];
}
