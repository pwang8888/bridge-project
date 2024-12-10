from web3 import Web3

def get_eth_keys(keyId = 0, filename = "/home/codio/workspace/.guides/tests/eth_mnemonic.txt"):
    """
    Generate a persistent Ethereum account
    keyId (integer) - which key to use
    filename - filename to read and store mnemonics

    Each mnemonic is stored on a separate line
    If fewer than (keyId+1) mnemonics have been generated, generate a new one and return that
    """
    w3 = Web3()
    try:
        w3.eth.account.enable_unaudited_hdwallet_features()
        f = open(filename,"r")
        #mnemonic_secrets = [line.strip() for line in f]
        mnemonic_secrets = f.read().splitlines()
        mnemonic_secret = mnemonic_secrets[keyId].rstrip()
        acct = w3.eth.account.from_mnemonic(mnemonic_secret)
        eth_pk = acct._address
        eth_sk = acct._private_key
        f.close()
    except Exception as e:
        print( e )
        print( "Generating account" )
        w3.eth.account.enable_unaudited_hdwallet_features()
        acct,mnemonic_secret = w3.eth.account.create_with_mnemonic()
        eth_pk = acct._address
        eth_sk = acct._private_key
        print(f"Private key: {eth_sk.hex()}" )
        print(f"Address: {eth_pk}" )
        print(f"mnemonic: {mnemonic_secret}" )
        f = open(filename, "a")
        f.write(f"{mnemonic_secret}\n" )
        f.close()

    #acct = w3.eth.account.privateKeyToAccount(eth_sk)
    return acct

if __name__ == "__main__":
    for i in range(4):
        acct = get_eth_keys(keyId=i)
        print( acct.address )
