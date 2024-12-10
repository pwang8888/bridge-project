# Bridge Project

This project implements a cross-chain bridge between the Avalanche Fuji testnet and the Binance Smart Chain (BSC) testnet. The bridge facilitates the seamless transfer of ERC-20 tokens between these two chains using smart contracts and an off-chain Python relayer.

---

## Overview

The Bridge Project consists of the following components:
1. **Source Chain Contract (Avalanche Fuji)**: Manages token deposits and withdrawals.
2. **Destination Chain Contract (BSC)**: Manages wrapped token minting and burning.
3. **Off-Chain Python Relayer**: Listens to events emitted by contracts and facilitates communication between the two chains.

---

## Features

- **Token Registration**: The bridge operator can register tokens eligible for transfer across the bridge.
- **Deposit and Wrap**: Users can deposit tokens on the source chain, triggering the minting of wrapped tokens on the destination chain.
- **Unwrap and Withdraw**: Users can burn wrapped tokens on the destination chain and withdraw the equivalent amount on the source chain.
- **Event-Driven Relayer**: A Python script listens for events (`Deposit` and `Unwrap`) and invokes the appropriate functions on the counterpart chain.

---

## Key Smart Contract Functions

### Source Contract (Avalanche Fuji)
1. **`registerToken(address tokenAddress)`**:
   - Registers a token for bridging.
   - Restricted to the bridge operator using OpenZeppelin's AccessControl.

2. **`deposit(address token, uint256 amount)`**:
   - Users deposit ERC-20 tokens.
   - Requires prior `approve` call to allow the bridge to pull tokens.

3. **`withdraw(address user, address token, uint256 amount)`**:
   - Transfers underlying tokens back to the user after burning wrapped tokens on the destination chain.
   - Callable only by the bridge operator.

### Destination Contract (BSC)
1. **`createToken(address sourceToken, string name, string symbol)`**:
   - Creates a wrapped token corresponding to a source chain token.
   - Callable only by the bridge operator.

2. **`wrap(address user, uint256 amount)`**:
   - Mints wrapped tokens for a user after a deposit on the source chain.
   - Callable only by the bridge operator.

3. **`unwrap(address token, uint256 amount)`**:
   - Burns wrapped tokens to facilitate withdrawal on the source chain.

---

## Token Transfer Flow

### From Source to Destination
1. **Token Registration**:
   - The bridge operator registers the ERC-20 token on the source chain.
   - The operator creates the corresponding wrapped token contract on the destination chain.

2. **Deposit**:
   - Users call the `approve` function on the ERC-20 token contract, allowing the source contract to transfer tokens.
   - Users call the `deposit` function on the source contract.
   - The source contract emits a `Deposit` event.

3. **Mint Wrapped Tokens**:
   - The Python relayer detects the `Deposit` event.
   - The relayer calls the `wrap` function on the destination contract.
   - Wrapped tokens are minted and sent to the user.

### From Destination to Source
1. **Unwrap**:
   - Users call the `unwrap` function on the destination contract to burn wrapped tokens.
   - The destination contract emits an `Unwrap` event.

2. **Withdraw**:
   - The Python relayer detects the `Unwrap` event.
   - The relayer calls the `withdraw` function on the source contract.
   - The source contract transfers the underlying tokens back to the user.

---

## Prerequisites

1. **Foundry**: A fast, portable, and modular development framework for Ethereum smart contracts.
2. **Python**: Required for the off-chain relayer script.
3. **Web3.py**: A Python library for interacting with Ethereum-compatible blockchains.

---

## Setup Instructions

### Install Foundry
If you haven’t already installed Foundry:
1. Install Foundryup, the Foundry toolchain installer:
   ```bash
   curl -L https://foundry.paradigm.xyz | bash

