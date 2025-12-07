from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware #Necessary for POA chains
from datetime import datetime
import json
import pandas as pd

WARDEN_PRIVATE_KEY = "0xdee8714a0d2837676be221317ac577abc804816c0b5305ef9198d5ea35256dd7"

def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """
        Load the contract_info file into a dictionary
        This function is used by the autograder and will likely be useful to you
    """
    try:
        with open(contract_info, 'r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]



def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    # This is different from Bridge IV where chain was "avax" or "bsc"
    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0

    
    w3_source = connect_to("source")
    w3_destination = connect_to("destination")

    src_info = get_contract_info("source", contract_info)
    destination_info = get_contract_info("destination", contract_info)

    src_address = Web3.to_checksum_address(src_info["address"])
    destination_address = Web3.to_checksum_address(destination_info["address"])
    src_abi = src_info["abi"]
    destination_abi = dst_info["abi"]

    source_contract = w3_source.eth.contract(address = src_address, abi = src_abi)
    destination_contract = w3_destination.eth.contract(address = destination_address, abi = destination_abi)

    if chain == "source":
      scan_w3 = w3_source
      scan_event = source_contract.events.Deposit

      action_w3 = w3_destination
      action_contract = destination_contract
      action_type = "wrap"

    else: 
      scan_w3 = w3_destination
      scan_event = destination_contract.events.Unwrap
      action_w3 = w3_source
      action_contract = source_contract
      action_type = "withdraw"

    latest = scan_w3.eth.get_block_number()
    from_block = max(latest - 5,0)
    to_block = latest


    event_filter = scan_event.create_filter(
      from_block = from_block,
      to_block = to_block,
      argument_filters={}
    )
    events = event_filter.get_all_entries()

    if not events:
      return 0 
    
    warden_account = action_w3.eth.account.from_key(WARDEN_PRIVATE_KEY)
    warden_addy = warden_account.address
    nonce = action_w3.eth.get_transaction_count(warden_addy)

    for i in events:
      args = i["args"]

      if chain == "source":
        token = args["token"]
        recipient = args["recipient"]
        amount = int(args["amount"])

        wrap_function = action_contract.functions.wrap(token, recipient, amount)

      else:
        underlying_token = args["underlying_token"]
        recipient = args["to"]
        amount = int(args["amount"])

        wrap_function = action_contract.functions.withdraw(underlying_token, recipient, amount)
        
      tx = wrap_function.build_transaction({
        "from": warden_addy,
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": action_w3.eth.gas_price,
      })

      nonce += 1

      signed = action_w3.eth.account.sign_transaction(tx, private_key = WARDEN_PRIVATE_KEY)
      tx_hash = action_w3.eth.send_raw_transaction(signed.rawTransaction)

    return 1

