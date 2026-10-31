import assert from "node:assert/strict";
import { randomBytes, createHmac } from "node:crypto";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:net";
import { after, before, test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const workspaceRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const bridgeSecret = randomBytes(48).toString("hex");
let baseUrl;
let apiProcess;
let apiOutput = "";
let requestTimestamp = Math.floor(Date.now() / 1000);

async function getFreePort() {
  const server = createServer();
  await new Promise((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  const { port } = server.address();
  await new Promise((resolveClose, reject) =>
    server.close((error) => (error ? reject(error) : resolveClose())),
  );
  return port;
}

function nextTimestamp() {
  requestTimestamp += 1;
  return String(requestTimestamp);
}

function makePayload() {
  const now = Date.now();
  const lastCandleTime = Math.floor(now / 300_000) * 300_000;
  const candles = Array.from({ length: 100 }, (_, index) => {
    const close = 2300 + index * 0.1;
    return {
      time: new Date(lastCandleTime - (99 - index) * 300_000).toISOString(),
      open: close - 0.05,
      high: close + 0.1,
      low: close - 0.1,
      close,
      volume: 100 + index,
    };
  });
  return {
    symbol: "XAUUSDm",
    timestamp: new Date(now).toISOString(),
    bid: 2300.1,
    ask: 2300.3,
    candles,
  };
}

function sign(timestamp, body) {
  return createHmac("sha256", bridgeSecret)
    .update(timestamp)
    .update(".")
    .update(body)
    .digest("hex");
}

async function postPayload(payload, options = {}) {
  const body = JSON.stringify(payload);
  const timestamp = nextTimestamp();
  const headers = {
    "content-type": "application/json",
    "x-forwarded-proto": options.protocol ?? "https",
    "x-bridge-timestamp": timestamp,
    "x-bridge-signature": options.signature ?? sign(timestamp, body),
  };
  if (options.noAuth) {
    delete headers["x-bridge-timestamp"];
    delete headers["x-bridge-signature"];
  }
  return fetch(`${baseUrl}/api/market-data/mt5-demo`, {
    method: "POST",
    headers,
    body,
  });
}

before(async () => {
  const port = await getFreePort();
  baseUrl = `http://127.0.0.1:${port}`;
  apiProcess = spawn(
    process.execPath,
    ["artifacts/api-server/dist/index.mjs"],
    {
      cwd: workspaceRoot,
      env: {
        ...process.env,
        PORT: String(port),
        NODE_ENV: "production",
        MT5_MARKET_DATA_BRIDGE_SECRET: bridgeSecret,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  apiProcess.stdout.setEncoding("utf8");
  apiProcess.stderr.setEncoding("utf8");
  apiProcess.stdout.on("data", (chunk) => {
    apiOutput += chunk;
  });
  apiProcess.stderr.on("data", (chunk) => {
    apiOutput += chunk;
  });

  let ready = false;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (apiProcess.exitCode !== null) {
      throw new Error(`API server exited during startup:\n${apiOutput}`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/healthz`);
      if (response.ok) {
        ready = true;
        break;
      }
    } catch {
      // The listener may not be ready yet.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 200));
  }
  assert.ok(ready, `API server did not become ready:\n${apiOutput}`);
});

after(async () => {
  if (!apiProcess || apiProcess.exitCode !== null) return;
  apiProcess.kill("SIGTERM");
  await Promise.race([
    once(apiProcess, "exit"),
    new Promise((resolveWait) => setTimeout(resolveWait, 3000)),
  ]);
  if (apiProcess.exitCode === null) apiProcess.kill("SIGKILL");
});

test("rejects non-HTTPS and missing authentication", async () => {
  const payload = makePayload();
  const insecure = await postPayload(payload, { protocol: "http" });
  assert.equal(insecure.status, 400);
  assert.match((await insecure.json()).error, /HTTPS/);

  const unauthenticated = await postPayload(payload, { noAuth: true });
  assert.equal(unauthenticated.status, 400);
});

test("rejects an invalid HMAC signature", async () => {
  const response = await postPayload(makePayload(), {
    signature: "0".repeat(64),
  });
  assert.equal(response.status, 401);
});

test("rejects invalid schema and any order-related field", async () => {
  const payload = makePayload();
  payload.order = { symbol: "XAUUSDm", side: "BUY" };
  const response = await postPayload(payload);
  assert.equal(response.status, 422);
  assert.match((await response.json()).error, /Only symbol/);
});

test("rejects stale quotes and malformed candle data", async () => {
  const stale = makePayload();
  stale.timestamp = new Date(Date.now() - 20_000).toISOString();
  const staleResponse = await postPayload(stale);
  assert.equal(staleResponse.status, 422);
  assert.match((await staleResponse.json()).error, /stale/);

  const invalidCandle = makePayload();
  invalidCandle.candles[99].high = invalidCandle.candles[99].low - 1;
  const invalidResponse = await postPayload(invalidCandle);
  assert.equal(invalidResponse.status, 422);
});

test("accepts fresh authenticated demo data and exposes only its quote", async () => {
  const response = await postPayload(makePayload());
  assert.equal(response.status, 202);
  const accepted = await response.json();
  assert.deepEqual(
    {
      accepted: accepted.accepted,
      symbol: accepted.symbol,
      candleCount: accepted.candleCount,
      dataOrigin: accepted.dataOrigin,
    },
    {
      accepted: true,
      symbol: "XAUUSDm",
      candleCount: 100,
      dataOrigin: "REAL",
    },
  );
  assert.ok(!JSON.stringify(accepted).includes(bridgeSecret));

  const brokerResponse = await fetch(`${baseUrl}/api/broker/status`);
  const broker = await brokerResponse.json();
  assert.equal(broker.connectionStatus, "CONNECTED");
  assert.equal(broker.dataOrigin, "REAL");
  assert.equal(broker.symbol, "XAUUSDm");
  assert.equal(broker.bid, 2300.1);
  assert.equal(broker.ask, 2300.3);
  assert.ok(Math.abs(broker.spread - 0.2) < 1e-9);
  assert.equal(broker.orderExecutionAllowed, false);
  assert.ok(!JSON.stringify(broker).includes(bridgeSecret));

  const startResponse = await fetch(`${baseUrl}/api/analysis/service/start`, {
    method: "POST",
  });
  assert.equal(startResponse.status, 200);
  try {
    let analysisStatus;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const statusResponse = await fetch(`${baseUrl}/api/analysis/service`);
      analysisStatus = await statusResponse.json();
      if (analysisStatus.analysis) break;
      await new Promise((resolveWait) => setTimeout(resolveWait, 250));
    }
    assert.equal(
      analysisStatus?.analysis?.source,
      "authenticated MT5 DEMO bridge (XAUUSDm M5)",
    );
    assert.equal(analysisStatus.analysis.candleCount, 100);
    assert.equal(analysisStatus.orderStatus, "DISABLED");
    assert.ok(!("price" in analysisStatus.analysis));
    assert.ok(!("entry_reference_price" in analysisStatus.analysis));
  } finally {
    await fetch(`${baseUrl}/api/analysis/service/stop`, { method: "POST" });
  }
});

test(
  "status hides previously accepted prices after the feed becomes stale",
  { timeout: 30_000 },
  async () => {
    await new Promise((resolveWait) => setTimeout(resolveWait, 16_000));
    const response = await fetch(`${baseUrl}/api/broker/status`);
    const broker = await response.json();
    assert.equal(broker.connectionStatus, "NOT_CONNECTED");
    assert.equal(broker.dataOrigin, "SIMULATED");
    assert.equal(broker.bid, null);
    assert.equal(broker.ask, null);
    assert.equal(broker.spread, null);
    assert.equal(broker.timestamp, null);
  },
);
