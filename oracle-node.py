import json
import time
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from solcx import compile_source, install_solc, get_installed_solc_versions, set_solc_version 

from web3 import Web3

# 🚨 Update these values before running!
alchemy_url = "https://eth-sepolia.g.alchemy.com/v2/8DB9KyZ9nk7uw4aiYq0vQQTdrIC1BkyV"  # Alchemy RPC URL for Sepolia
CMC_API = "f4bc6bd5-c151-445c-88ab-2223e250eddc"  # CoinMarketCap API Key
my_account = "0x368468517699A568a78785904A0C1CE31356c817"  # Ethereum address (from Metamask)
private_key = "b39f72a94c1b3386eaec2fd8076eaa3c6a04b0cdeeaa80588568a0037f17c1c4"  # Private key for signing transactions (keep secure!)

# Path to Solidity contract file
MyOracleSource = "MyOracle.sol"

# ✅ Fetch ETH price from CoinMarketCap API
def get_eth_price():
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    parameters = {'symbol': 'ETH', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API}

    session = Session()
    session.headers.update(headers)

    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        return data['data']['ETH']['quote']['USD']['price']
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(f"Error fetching price: {e}")
        return None

# ✅ Compile the Solidity contract
def compile_contract(w3):
    with open(MyOracleSource, 'r') as file:
        oracle_code = file.read()

    # Compile Solidity contract
    compiled_sol = compile_source(oracle_code, output_values=['abi', 'bin'])
    contract_id, contract_interface = compiled_sol.popitem()
    bytecode = contract_interface['bin']  # Contract binary
    abi = contract_interface['abi']  # Contract ABI

    return w3.eth.contract(abi=abi, bytecode=bytecode), abi

# ✅ Deploy the contract on Sepolia testnet
def deploy_oracle(w3, contract):
    deploy_txn = contract.constructor().build_transaction({
        'from': my_account,
        'gas': 3000000,
        'gasPrice': w3.to_wei('20', 'gwei'),
        'nonce': w3.eth.get_transaction_count(my_account),
    })

    signed_txn = w3.eth.account.sign_transaction(deploy_txn, private_key=private_key)
    print("Deploying Contract...")
    
    # ✅ Fix: Use `raw_transaction` instead of `rawTransaction`
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

    txn_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return txn_receipt.contractAddress  # Return the deployed contract address

    deploy_txn = contract.constructor().build_transaction({
        'from': my_account,
        'gas': 3000000,
        'gasPrice': w3.to_wei('20', 'gwei'),
        'nonce': w3.eth.get_transaction_count(my_account),
    })

    signed_txn = w3.eth.account.sign_transaction(deploy_txn, private_key=private_key)
    print("Deploying Contract...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    txn_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return txn_receipt.contractAddress  # Return deployed contract address

# ✅ Update ETH price on the blockchain
def update_oracle(w3, contract, eth_price):
    set_txn = contract.functions.setETHUSD(int(eth_price * 100)).build_transaction({
        'from': my_account,
        'gas': 200000,
        'gasPrice': w3.to_wei('20', 'gwei'),
        'nonce': w3.eth.get_transaction_count(my_account),
    })

    signed_txn = w3.eth.account.sign_transaction(set_txn, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    txn_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return txn_receipt  # Return transaction receipt

# ✅ Main function to execute the script
def main():
    # Install Solidity compiler & connect to Sepolia testnet
    #install_solc('0.8.17')
    set_solc_version('0.8.17')
    print(get_installed_solc_versions())
    w3 = Web3(Web3.HTTPProvider(alchemy_url))
    w3.eth.default_account = my_account  # Set default account

    if not w3.is_connected():
        print('Not connected to Alchemy')
        exit(-1)

    # Compile & Deploy Contract
    MyOracle, abi = compile_contract(w3)
    oracle_address = deploy_oracle(w3, MyOracle)
    print(f"MyOracle contract deployed at: {oracle_address}")

    # Connect to deployed contract
    oracle_contract = w3.eth.contract(address=oracle_address, abi=abi)
    
    # 🔥 Monitor contract for price update requests
    event_filter = oracle_contract.events.RequestPriceUpdate.create_filter(from_block='latest')


    while True:
        print("Waiting for price update requests...")
        for event in event_filter.get_new_entries():
            if event.event == "RequestPriceUpdate":
                print("Updating ETH price...")
                eth_price = get_eth_price()
                if eth_price:
                    txn_receipt = update_oracle(w3, oracle_contract, eth_price)
                    print(f"ETH price updated: {eth_price} USD - TXN Hash: {txn_receipt.transactionHash.hex()}")
        time.sleep(5)  

# Run the script
if __name__ == "__main__":
    main()
