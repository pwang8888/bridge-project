import json
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import decode_hex

def connect_to(chain):
    """
    Connects to the blockchain network.
    """
    rpc_urls = {
        "bsc": "https://data-seed-prebsc-1-s1.binance.org:8545/",
        "avax": "https://api.avax-test.network/ext/bc/C/rpc",
    }
    if chain not in rpc_urls:
        raise ValueError(f"Unsupported chain: {chain}")
    rpc_url = rpc_urls[chain]
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to {chain} at {rpc_url}")
    print(f"Successfully connected to {chain} blockchain.")
    return w3


def get_contract_info(file, contract_type):
    with open(file, "r") as f:
        contract_data = json.load(f)
        return contract_data[contract_type]["address"], contract_data[contract_type]["abi"]


def load_erc20_tokens(csv_file):
    """
    Loads token addresses from a CSV file.
    """
    tokens = []
    with open(csv_file, "r") as file:
        for line in file.readlines():
            chain, address = line.strip().split(",")
            tokens.append({"chain": chain, "address": address})
    return tokens


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



def register_tokens_on_source(tokens, source_contract, w3, account, private_key):
    """
    Registers tokens on the Source contract.
    """
    for token in tokens:
        if token["chain"].lower() == "avax":
            token_address = token["address"]
            print(f"Registering token {token_address} on Source contract...")
            try:
                send_transaction(w3, source_contract.functions.registerToken, [token_address], account, private_key)
            except Exception as e:
                print(f"Failed to register token {token_address}: {str(e)}")


def create_tokens_on_destination(tokens, destination_contract, w3, account, private_key):
    """
    Creates wrapped tokens on the Destination contract.
    """
    for token in tokens:
        if token["chain"].lower() == "avax":
            token_address = token["address"]
            token_name = f"Wrapped-{token_address[-4:]}"
            token_symbol = f"W{token_address[-4:]}"
            print(f"Creating token {token_address} on Destination contract...")
            try:
                # Simulate the function call
                print(f"Simulating createToken with: token_address={token_address}, token_name={token_name}, token_symbol={token_symbol}")
                result = destination_contract.functions.createToken(token_address, token_name, token_symbol).call({"from": account.address})
                print(f"Simulation result: {result}")

                # Send the transaction
                send_transaction(w3, destination_contract.functions.createToken, [token_address, token_name, token_symbol], account, private_key)
            except Exception as e:
                if hasattr(e, 'response') and e.response:
                    error_message = decode_hex(e.response['error']['message'])
                    print(f"Revert Reason: {error_message}")
                print(f"Failed to create token {token_address}: {str(e)}")


def main():
    json_file = "contract_info.json"
    csv_file = "erc20s.csv"

    # Load token data
    tokens = load_erc20_tokens(csv_file)

    private_key = "f447cac1243f3e6eaa439a774c3fd4203166ff2859b115d40670b2da163a018a"
    w3_bsc = connect_to("bsc")
    w3_avax = connect_to("avax")
    account = w3_avax.eth.account.from_key(private_key)

    source_address, source_abi = get_contract_info(json_file, "source")
    destination_address, destination_abi = get_contract_info(json_file, "destination")

    source_contract = w3_avax.eth.contract(address=source_address, abi=source_abi)
    destination_contract = w3_bsc.eth.contract(address=destination_address, abi=destination_abi)

    register_tokens_on_source(tokens, source_contract, w3_avax, account, private_key)
    create_tokens_on_destination(tokens, destination_contract, w3_bsc, account, private_key)


if __name__ == "__main__":
    main()
