# solve_99

This folder is a standalone note for preserving a debugging method. It is not part of the trading system spec.

## Goal

Teach weaker agents how to find an issue that another agent failed to locate, especially when the failure comes from API drift, environment mismatch, or false assumptions.

## Core Rule

Do not argue with the symptom. Freeze the symptom, reduce the unknowns, and verify each assumption against a primary source and a minimal live repro.

## Method

### 1. Freeze the exact failure

Write down:

- what action failed
- the exact endpoint / module / function
- the exact exchange or service response
- whether the failure is deterministic or intermittent
- account mode and environment flags

If you cannot state the failure in one sentence, you are still guessing.

Example from this case:

- Market entry worked
- stop placement failed
- previous path used `/fapi/v1/order`
- account was Binance USD-M Futures, Hedge Mode, live trading with function-test gating

### 2. Use primary sources only

For exchange or SDK behavior, stop relying on memory, forum posts, or stale copied code.

Use:

- official API docs
- official changelog when available
- actual live response from the service

In this case, the key source was Binance official docs:

- `POST /fapi/v1/algoOrder`
- `GET /fapi/v1/openAlgoOrders`
- `GET /fapi/v1/allOrders`

That immediately exposed that the native stop route had drifted away from the old assumption.

### 3. Compare implementation to docs field by field

Do a direct diff between:

- current code path
- official endpoint
- required params
- forbidden params
- account-mode constraints

Typical misses:

- wrong endpoint
- deprecated order type
- wrong parameter name
- `reduceOnly` used where Hedge Mode forbids it
- stop order exists, but you are looking in the wrong "open orders" endpoint

### 4. Build the smallest safe repro

Do not debug the whole app first.

Create the smallest possible test that answers one question at a time:

1. Can I read account state?
2. Can I place the target order with the exact documented payload?
3. Can I query that order from the correct endpoint?
4. Can I confirm the final lifecycle event?

The repro should be narrow enough that a failure has only a few causes left.

### 5. Verify environment constraints early

Before changing code, confirm:

- exchange type
- one-way mode vs Hedge Mode
- live vs testnet
- feature flags
- symbol gating
- private API availability

Many "logic bugs" are actually environment mismatches.

### 6. Add temporary observability, but do not leak secrets

You need enough logging to answer:

- what payload was sent
- what response came back
- what state the exchange shows now

But redact tokens, signed URLs, and chat bot credentials. If the logging framework leaks request URLs, lower that logger level or sanitize the output.

### 7. Prove the fix outside the happy path

A fix is not done when the order is accepted once.

Also verify:

- state restoration after restart
- monitoring path
- trigger / fill detection
- stale record cleanup
- fallback behavior if the native object disappears

### 8. Convert the discovery into permanent artifacts

Once the real cause is proven:

- patch the production code
- add regression tests
- update the README or handoff
- record the reasoning so another agent does not rediscover it from zero

If the knowledge stays only in chat, it will be lost.

## Case Study Summary

### Symptom

BTCUSDT market buy succeeded, but the stop logic failed to place a valid native stop on Binance USD-M Futures.

### Wrong assumption

The previous logic assumed native stop should still be created via `POST /fapi/v1/order`.

### What actually worked

The current Binance path for this use case was:

- create native stop via `POST /fapi/v1/algoOrder`
- use `algoType=CONDITIONAL`
- use `type=STOP_MARKET`
- set `closePosition=true`
- query open native stop objects via `GET /fapi/v1/openAlgoOrders`

### Why the issue was easy to miss

- market entry was valid, so the system looked partially healthy
- the old endpoint looked plausible
- normal open-order queries did not show algo orders
- account mode rules added noise around `reduceOnly`

### What closed the gap

- official docs first
- minimal live repro second
- field-by-field payload comparison
- then end-to-end validation on a real BTCUSDT function test

## Short Checklist

Before saying "I cannot find the problem", the agent should be able to answer:

1. What exact call fails?
2. What exact response comes back?
3. What official doc page governs that call today?
4. What is different between the code payload and the documented payload?
5. Can a minimal direct repro confirm or reject that difference?
6. Can the fixed path be observed from creation to completion?

If any answer is missing, the investigation is incomplete.
