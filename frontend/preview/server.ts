import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import type { Connect, Plugin } from "vite";

import type { ReviewResponse } from "../src/contracts.ts";

/** Development preview only. Never mounted by FastAPI or the normal build. */
export function fixturePreview(): Plugin {
  const dashboard = readFileSync(
    new URL("./dashboard.json", import.meta.url),
    "utf8",
  );
  const clients = new Set<string>(Object.keys(JSON.parse(dashboard).pre_reads));
  const middleware: Connect.NextHandleFunction = async (req, res, next) => {
    const path = req.url?.split("?")[0];
    if (path !== "/preview/dashboard" && path !== "/preview/reviews") {
      next();
      return;
    }
    const send = (status: number, body: unknown) => {
      res.writeHead(status, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      });
      res.end(JSON.stringify(body));
    };
    if (path === "/preview/dashboard" && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      });
      res.end(dashboard);
      return;
    }
    if (path !== "/preview/reviews" || req.method !== "POST") {
      send(405, { detail: "Method not allowed" });
      return;
    }
    try {
      const chunks: Buffer[] = [];
      let size = 0;
      for await (const chunk of req) {
        const bytes = Buffer.from(chunk);
        size += bytes.length;
        if (size > 16_384) {
          send(413, { detail: "Preview review is too large" });
          return;
        }
        chunks.push(bytes);
      }
      const body: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      if (!body || typeof body !== "object") {
        send(422, { detail: "Invalid preview review" });
        return;
      }
      const { client_id, action, text = "" } = body as Record<string, unknown>;
      if (
        typeof client_id !== "string" ||
        !clients.has(client_id) ||
        (action !== "Approve" && action !== "Edit" && action !== "Reject") ||
        typeof text !== "string" ||
        [...text].length > 1200 ||
        (action === "Edit" && !text.trim())
      ) {
        send(422, { detail: "Invalid preview review" });
        return;
      }
      // Echo a simulated receipt. There is deliberately no ledger or persistence.
      const response: ReviewResponse = {
        review: {
          client_id,
          action,
          text,
          review_id: `preview-${randomUUID()}`,
          timestamp: new Date().toISOString(),
          rm: "Priscilla Ong (preview)",
        },
      };
      send(200, response);
    } catch {
      send(400, { detail: "Invalid preview review JSON" });
    }
  };
  return {
    name: "fixture-preview",
    configureServer: (server) => {
      server.middlewares.use(middleware);
    },
    configurePreviewServer: (server) => {
      server.middlewares.use(middleware);
    },
  };
}
