import sys
import json
import time
import random
import pandas as pd
from web3 import Web3, constants
from os import path
from pathlib import Path
from web3.middleware import geth_poa_middleware  # Necessary for POA chains
from gen_keys import get_eth_keys


def connect_to(chain):
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet

    if chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet

    if chain in ['avax', 'bsc']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3


# def getContractInfo(chain):
#    p = Path(__file__).with_name(contract_info)
#    try:
#        with p.open('r')  as f:
#            contracts = json.load(f)
#    except Exception as e:
#        print( "Failed to read contract info" )
#        print( "Please contact your instructor" )
#        print( e )
#        sys.exit(1)
#
#    return contracts[chain]

########################################
contract_info = "contract_info.json"
source_chain = 'avax'
destination_chain = 'bsc'
source_w3 = connect_to(source_chain)
destination_w3 = connect_to(destination_chain)


########################################

def get_erc20_abi():
    """
    Return the ABI for our ERC20 contract
    First, it tries to read the ABI from a local file
    If the file does not exist it compiles the ERC20 contract, writes the ABI to
    disk to avoid future compilations, and returns the ABI
    """

    # Try to read the ABI from a local file
    ERC20_ABI_JSON = Path(__file__).with_name("ERC20ABI.json")
    if path.exists(ERC20_ABI_JSON):
        with open(ERC20_ABI_JSON, 'r') as f:
            return json.load(f)
    else:
        print(f"Error ERC20 ABI file does not exist")
        print(f"Contact your instructor")
        sys.exit(0)


def get_erc20s(w3, chain, n):
    """
    w3 - web3 instance (connected to the appropriate blockchain)
    chain (string) - which blockchain to use (e.g. 'avax', 'bsc')
    n (integer) - how many contracts to return

    Returns n ERC20 contract objects on the chain given by the 'chain' argument
    It tries to read known contract addresses from the file "erc20s.csv"
    """

    try:
        df = pd.read_csv("erc20s.csv")
        contracts = df.loc[df['chain'] == chain]['address'].unique()
    except Exception as e:
        print(f"Error: unable to read ERC20 contracts")
        print(f"Contact your instructor")
        print(e)
        sys.exit(0)

    num_deployed = len(contracts)
    if num_deployed < n:
        print(f"Error: tell your instructor to deploy more ERC20 contracts to {chain}")
        n = num_deployed

    ERC20_ABI = get_erc20_abi()
    tokens = [w3.eth.contract(abi=ERC20_ABI, address=c) for c in contracts[:n]]
    return tokens


def get_wrapped_token(token):
    """
        token - (contract object) underlying token on source chain
        Returns a contract object corresponding to the wrapped version of this asset on the destination chain
    """
    try:
        wrapped_token_address = destination_contract.functions.wrapped_tokens(token.address).call()
    except Exception as e:
        print(f"Failed to get wrapped token for {token.address} on contract {destination_contract.address}")
        print(e)
        return None
    ERC20_ABI = get_erc20_abi()
    try:
        wrapped_token = destination_w3.eth.contract(abi=ERC20_ABI, address=wrapped_token_address)
    except Exception as e:
        print(
            f"Failed to create token contract object for {wrapped_token_address} "
            f"on contract {destination_contract.address}\n{e}")
        return None

    return wrapped_token


def sign_and_send(contract, function, signer, argdict, confirm=True, nonce_offset=0):
    """
        contract - (contract object) 
        functin - (string) the function to be called on the contract
        signer - (account object) the account that should initiate the transaction
        argdict - (dictionary) the function arguments as key-value pairs
        confirm - (boolean) whether to wait for confirmation from the chain
        nonce_offset - (int) signAndSend gets the signer's nonce from on-chain, so if you call it multiple times
        in rapid succession, the later transactions will fail.  This allow you to manually increment the nonce if
        you know you're going to call the function repeatedly
    """
    w3 = contract.w3
    nonce = w3.eth.get_transaction_count(signer.address)
    nonce += nonce_offset
    contract_func = getattr(contract.functions, function)
    try:
        tx = contract_func(**argdict).build_transaction(
            {'nonce': nonce, 'gasPrice': w3.eth.gas_price, 'from': signer.address,
             'gas': 10 ** 6})  # Must set gas price (https://github.com/ethereum/web3.py/issues/2307)
    except Exception as e:
        print(f"signAndSend: failed to build transaction (function = {function})")
        print(e)
        return None
    signed_tx = signer.sign_transaction(tx)

    try:
        w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    except Exception as e:
        print(f"signAndSend: failed to send transaction (function = {function})")
        print(e)
        return None

    if confirm:
        tx_receipt = w3.eth.wait_for_transaction_receipt(signed_tx.hash)
        if tx_receipt.status:
            print(f"Transaction confirmed for '{function}' at block {tx_receipt.blockNumber}")
        else:
            print(f"Transaction failed '{function}' in signAndSend")
            print(signed_tx.hash.hex())

    return signed_tx.hash.hex()


def ensure_balance(token, user, bal):
    """
        token - (contract object) an ERC20 token
        user - (address)
        bal - (int)
        Ensure the address "user" has a balance of at least bal in the ERC20 token.
        If the user's balance is below bal, new tokens are minted
    """
    minter = get_eth_keys(keyId=1)

    current_balance = token.functions.balanceOf(user).call()
    if current_balance >= bal:
        return True

    try:
        is_minter = token.functions.hasRole(token.functions.MINTER_ROLE().call(), minter.address)
    except Exception as e:
        print(f"Failed to call 'hasRole'")
        print("Contact your instructor")
        print(e)
        return False

    if not is_minter:
        print(f"{minter.address} is not allowed to mint tokens on {token.address}")
        print("Contact your instructor")
        return False

    print("Grader low on tokens, topping up before we check student contracts")
    print(f"Minting {bal - current_balance} {token.functions.symbol().call()} tokens to {user}")
    sign_and_send(token, 'mint', minter, {'to': user, 'amount': bal - current_balance})


def check_token_registration(deposits, points):
    """
       check erc20s are registered on contracts
    """
    points_per = points / (2 * len(deposits))
    for d in deposits:
        token = d['token']  # Contract object (not address)
        sender = d['sender']  # Account object (not address)

        ensure_balance(token, sender.address, 10 ** 6)
        if not source_contract.functions.approved(token.address).call():
            print(f"Error: you need to call registerToken({token.address}) Before submitting your assignment")
            points -= points_per
        if constants.ADDRESS_ZERO == destination_contract.functions.wrapped_tokens(token.address).call():
            print(f"Error: you need to call createToken({token.address}) Before submitting your assignment")
            points -= points_per
        return points


def check_contract_addresses(source, destination):
    """
        check student provided "contract_info.json" contracts against defaults
    """
    default_source = "0x2849A1F9e4700BEe779232396FD803cdcA7d0cde"
    default_destination = "0x99Ab2ae5053244E85BC0fbE1A311740295c2afEc"
    unique_addresses = True

    if default_source == source:
        print(f"Error: your git repo 'contract_info.json' has the default 'source' address {source}")
        print("you need to deploy your own source contract and update 'contract_info.json'")
        unique_addresses = False
    if default_destination == destination:
        print(f"Error: your git repo 'contract_info.json' has the default 'destination' address {destination}")
        print("you need to deploy your own destination contract and update 'contract_info.json'")
        unique_addresses = False

    return unique_addresses


def make_deposits(deposits):
    """
        deposits - (list of dictionaries)  
        Make deposits on the source chain
    """

    for d in deposits:
        token = d['token']  # Contract object (not address)
        sender = d['sender']  # Account object (not address)
        receiver = d['receiver']  # address
        amount = d['amount']  # int

        try:
            transaction_hash = sign_and_send(token, "approve", sender,
                                             {'spender': source_contract.address, 'amount': amount})
            print(f"Approval at {transaction_hash}")
        except Exception as e:
            print(f"Error: Failed to approve token transfer\nContact your instructor\n{e}")

        try:
            print(f"public_validate: sourceContract.address = {source_contract.address}")
            transaction_hash = sign_and_send(source_contract, "deposit", sender,
                                             {'_token': token.address,
                                              '_recipient': receiver,
                                              '_amount': amount})
            print(f"Deposit transaction Hash = {transaction_hash}")
        except Exception as e:
            print(f"Error: deposit transaction failed on source chain\n{e}")


def make_withdrawals(withdrawals):
    """
        withdrawals - (list of dictionaries)  
        Make withdrawals on the destination chain
    """

    for d in withdrawals:
        token = d['token']  # Contract object of wrapped token (not address)
        sender = d['sender']  # Account object (not address)
        receiver = d['receiver']  # address
        amount = d['amount']  # int

        # No need to approve withdrawal, the bridge can withdraw without approvals to save gas
        try:
            print(f"public_validate: destinationContract.address = {destination_contract.address}")
            transaction_hash = sign_and_send(destination_contract, "unwrap", sender,
                                             {'_wrapped_token': token.address,
                                              '_recipient': receiver,
                                              '_amount': amount})
            print(f"Unwrap transaction Hash = {transaction_hash}")
        except Exception as e:
            print(f"Error: unwrap transaction failed on destination chain")
            print(e)


def check_for_wrap():
    end_block = destination_w3.eth.get_block_number()
    start_block = end_block - 5
    print(f"Autograder scanning blocks {start_block} - {end_block} on destination")
    event_filter = destination_contract.events.Wrap.create_filter(fromBlock=start_block, toBlock=end_block,
                                                                  argument_filters={})
    events = event_filter.get_all_entries()
    print(f"Autograder found {len(events)} events")

    wrap_events = []
    for evt in events:
        data = {
            'event': evt.event,  # Wrap
            'block_number': evt.blockNumber,
            'underlying_token': evt.args['underlying_token'],
            'wrapped_token': evt.args['wrapped_token'],
            'to': evt.args['to'],
            'amount': evt.args['amount'],
            'transactionHash': evt.transactionHash.hex(),
            'address': evt.address,
        }
        print(json.dumps(data, indent=2))
        wrap_events.append(data)

    return wrap_events


def check_for_withdrawal():
    end_block = source_w3.eth.get_block_number()
    start_block = end_block - 5
    print(f"Autograder scanning blocks {start_block} - {end_block} on source")
    event_filter = source_contract.events.Withdrawal.create_filter(fromBlock=start_block, toBlock=end_block,
                                                                   argument_filters={})
    events = event_filter.get_all_entries()
    print(f"Autograder found {len(events)} Withdrawal events")

    withdrawal_events = []
    for evt in events:
        data = {
            'event': evt.event,  # Withdrawal
            'block_number': evt.blockNumber,
            'token': evt.args['token'],
            'recipient': evt.args['recipient'],
            'amount': evt.args['amount'],
            'transactionHash': evt.transactionHash.hex(),
            'address': evt.address,
        }
        print(json.dumps(data, indent=2))
        withdrawal_events.append(data)
    return withdrawal_events


def validate(dir_string):
    sys.path.append(dir_string)

    # Define contract instances
    global source_contract
    global destination_contract
    print("----- Calling student 'bridge.getContractInfo()' -----")
    try:
        from bridge import getContractInfo
        source = getContractInfo('source')
        source_contract = source_w3.eth.contract(abi=source['abi'], address=source['address'])
        destination = getContractInfo('destination')
        destination_contract = destination_w3.eth.contract(abi=destination['abi'], address=destination['address'])
    except Exception as e:
        print(f"Error running getContractInfo")
        print(e)
        return 0

    # Points awarded for deploying contracts
    contract_points = 10
    if not check_contract_addresses(source['address'], destination['address']):
        return 0

    user_a = get_eth_keys(keyId=0)
    user_b = get_eth_keys(keyId=3)

    tokens = get_erc20s(source_w3, source_chain, 2)
    deposits = [{'token': tokens[0], 'sender': user_a, 'receiver': user_b.address, 'amount': random.randint(10, 1000)}]
    withdrawals = [
        {'token': get_wrapped_token(t['token']), 'sender': user_b, 'receiver': user_a.address, 'amount': t['amount']}
        for t
        in deposits]

    print("\n----- AutoGrader checking student has registered / created tokens -----")
    # Points for registering tokens
    token_points = 10
    # Check if student has registered tokens and award up to "token_points" for tokens registered
    points_earned = check_token_registration(deposits, token_points)
    if points_earned < token_points:  # If student has not completed registration exit grader
        print(f"Score = {points_earned + contract_points}")
        return points_earned + contract_points

    # If the code hasn't returned at this point then the final score
    # will be the greater of "points_earned + contract_points" or
    # "scaled_score"

    print("\n----- AutoGrader sending deposits to student Source contract -----")
    make_deposits(deposits)
    time.sleep(5)

    print("\n----- Calling student 'bridge.scanBlocks()' -----")
    try:
        from bridge import scanBlocks
        scanBlocks('source')  # Run the student's code
    except Exception as e:
        print(f"Error running scanBlocks('source')")
        print(e)
        return 0

    print("\n----- AutoGrader searching for Wrap events on student Destination contract -----")
    time.sleep(5)
    # Now we search the destination chain for Wrap events
    wrap_events = check_for_wrap()
    if len(wrap_events) == 0:
        time.sleep(5)
        wrap_events = check_for_wrap()
    score = 0
    for d in deposits:
        for w in wrap_events:
            if d['receiver'] == w['to'] and d['amount'] == w['amount'] and d['token'].address == w['underlying_token']:
                score += 1
                break
            else:
                print(f"{d['receiver']} ?= {w['to']}")
                print(f"{d['amount']} ?= {w['amount']}")
                print(f"{d['token']} ?= {w['underlying_token']}")

    ############################################################
    # Now we test the reverse direction
    # We make withdrawals on the destination chain and check if the message gets passed back to the source chain
    print("\n----- AutoGrader sending Unwrap to student Destination contract -----")
    make_withdrawals(withdrawals)
    time.sleep(5)
    print("\n----- Calling student 'bridge.scanBlocks()' -----")
    try:
        from bridge import scanBlocks
        scanBlocks('destination')  # Run the student's code
    except Exception as e:
        print(f"Error running scanBlocks('destination')")
        print(e)
        return 0

    # Now we search the source chain for Withdraw events
    print("\n----- AutoGrader searching for Withdraw events on student Source contract -----")
    time.sleep(5)
    withdrawal_events = check_for_withdrawal()
    if len(withdrawal_events) == 0:
        time.sleep(5)
        withdrawal_events = check_for_wrap()

    for u in withdrawals:
        for w in withdrawal_events:
            if u['receiver'] == w['recipient'] and \
                    u['amount'] == w['amount'] and \
                    destination_contract.functions.underlying_tokens(u['token'].address).call() == w['token']:
                score += 1
                break
            else:
                print(f"{u['receiver']} ?= {w['recipient']}")
                print(f"{u['amount']} ?= {w['amount']}")
                print(f"{destination_contract.functions.underlying_tokens(u['token'].address).call()} ?= {w['token']}")

    scaled_score = 100.0 * (float(score) / (2 * len(deposits)))
    # Added logic to award points for registering tokens and updating default contracts
    if scaled_score < points_earned + contract_points:
        scaled_score = points_earned + contract_points
    print(f"Score = {scaled_score}")
    return scaled_score


if __name__ == "__main__":
    # validate("/home/codio/workspace/")
    validate(".")
