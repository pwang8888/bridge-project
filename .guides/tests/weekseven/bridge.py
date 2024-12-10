from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware  # Necessary for POA chains
import json
import sys
from pathlib import Path

# Constants
source_chain = 'avax'
destination_chain = 'bsc'
contract_info = "contract_info.json"
private_key = "f447cac1243f3e6eaa439a774c3fd4203166ff2859b115d40670b2da163a018a"


def connectTo(chain):
    """
    Connects to the blockchain network.
    """
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    elif chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet
    else:
        raise ValueError(f"Unsupported chain: {chain}")

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # Add middleware for POA compatibility

    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to {chain} blockchain at {api_url}")
    print(f"Successfully connected to {chain} blockchain.")
    return w3


def getContractInfo(chain):
    """
    Load the contract_info file into a dictionary.
    """
    p = Path(__file__).with_name(contract_info)
    try:
        with p.open('r') as f:
            contracts = json.load(f)
    except Exception as e:
        print("Failed to read contract info")
        print("Please contact your instructor")
        print(e)
        sys.exit(1)

    return contracts[chain]


def send_transaction(w3, contract_function, args, account, private_key, gas_limit=1500000):
    """
    Sends a transaction to the blockchain.
    """
    try:
        # Estimate gas
        gas_estimate = contract_function(*args).estimate_gas({"from": account.address})
        print(f"Estimated Gas: {gas_estimate}")

        if gas_limit < gas_estimate:
            print(f"Gas limit ({gas_limit}) is too low. Using estimated gas: {gas_estimate}")
            gas_limit = gas_estimate + 10000  # Add a buffer for safety

        # Build and send transaction
        nonce = w3.eth.get_transaction_count(account.address, "pending")
        gas_price = w3.eth.gas_price
        tx = contract_function(*args).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price,
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            print(f"Transaction successful. TX Hash: {receipt.transactionHash.hex()}")
            return receipt.transactionHash.hex()
        else:
            print(f"Transaction failed. Receipt: {receipt}")
            return None
    except Exception as e:
        print(f"Transaction failed: {str(e)}")
        return None


def scanBlocks(chain):
    """
    Scan the last 5 blocks of the source and destination chains.
    """
    if chain == "source":
        w3 = connectTo(source_chain)
        contract_info = getContractInfo("source")
        event_name = "Deposit"
    elif chain == "destination":
        w3 = connectTo(destination_chain)
        contract_info = getContractInfo("destination")
        event_name = "Unwrap"
    else:
        print(f"Invalid chain: {chain}")
        return

    contract_address = contract_info["address"]
    contract_abi = contract_info["abi"]
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    end_block = w3.eth.get_block_number()
    start_block = max(0, end_block - 4)  # Ensure we don't go below block 0
    print(f"Scanning {chain} chain for {event_name} events from blocks {start_block} to {end_block}...")

    try:
        event_filter = contract.events[event_name].create_filter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()

        for evt in events:
            print(f"Found {event_name} event: {evt}")

            if chain == "source" and event_name == "Deposit":
                token = evt.args["token"]
                recipient = evt.args["recipient"]
                amount = evt.args["amount"]
                handle_wrap_on_destination(token, recipient, amount)
            elif chain == "destination" and event_name == "Unwrap":
                underlying_token = evt.args["underlying_token"]
                wrapped_token = evt.args["wrapped_token"]
                frm = evt.args["frm"]
                to = evt.args["to"]
                amount = evt.args["amount"]
                handle_withdraw_on_source(underlying_token, to, amount)

    except Exception as e:
        print(f"Error scanning blocks on {chain}: {e}")


def handle_wrap_on_destination(token, recipient, amount):
    """
    Handles a Deposit event by calling the wrap function on the destination chain.
    """
    print(f"Calling wrap on destination chain for token={token}, recipient={recipient}, amount={amount}...")
    try:
        destination_w3 = connectTo(destination_chain)
        destination_contract_info = getContractInfo("destination")
        destination_contract = destination_w3.eth.contract(
            address=destination_contract_info["address"], abi=destination_contract_info["abi"]
        )
        account = destination_w3.eth.account.from_key(private_key)

        tx_hash = send_transaction(
            destination_w3,
            destination_contract.functions.wrap,
            [token, recipient, amount],
            account,
            private_key
        )
        if tx_hash:
            print(f"wrap() transaction successful. TX Hash: {tx_hash}")
        else:
            print("wrap() transaction failed.")
    except Exception as e:
        print(f"Error calling wrap on destination chain: {e}")

def handle_withdraw_on_source(underlying_token, recipient, amount):
    print(f"Calling withdraw on source chain for underlying_token={underlying_token}, recipient={recipient}, amount={amount}...")
    try:
        source_w3 = connectTo(source_chain)
        source_contract_info = getContractInfo("source")
        source_contract = source_w3.eth.contract(
            address=source_contract_info["address"], abi=source_contract_info["abi"]
        )
        account = source_w3.eth.account.from_key(private_key)

        tx_hash = send_transaction(
            source_w3,
            source_contract.functions.withdraw,
            [underlying_token, recipient, amount],
            account,
            private_key
        )
        if tx_hash:
            print(f"withdraw() transaction successful. TX Hash: {tx_hash}")
        else:
            print("withdraw() transaction failed.")
    except Exception as e:
        print(f"Error calling withdraw on source chain: {e}")


if __name__ == "__main__":
    scanBlocks("source")
    scanBlocks("destination")
