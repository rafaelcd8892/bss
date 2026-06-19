import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type PlayByPlayResult = components["schemas"]["SimulateGamePlayByPlayResult"];
export type Play = components["schemas"]["PlayByPlayEvent"];
export type GameSummary = components["schemas"]["SimulateGameResult"];
