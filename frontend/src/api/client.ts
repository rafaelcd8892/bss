import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type PlayByPlayResult = components["schemas"]["SimulateGamePlayByPlayResult"];
export type Play = components["schemas"]["PlayByPlayEvent"];
export type GameSummary = components["schemas"]["SimulateGameResult"];
export type StatLeadersResult = components["schemas"]["StatLeadersResponse"];
export type StatLeader = components["schemas"]["StatLeader"];
export type LeaderMetric = StatLeadersResult["metric"];
export type MetricComparison = components["schemas"]["MetricComparison"];
export type ComparePlayersResult = components["schemas"]["ComparePlayersResult"];
