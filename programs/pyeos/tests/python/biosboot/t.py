import os
import json
import numpy

import eosapi
import wallet

from common import producer
import initeos

system_accounts = [
    'eosio.bpay',
    'eosio.msig',
    'eosio.names',
    'eosio.ram',
    'eosio.ramfee',
    'eosio.saving',
    'eosio.stake',
    'eosio.token',
    'eosio.vpay',
]

pub = 'EOS8Znrtgwt8TfpmbVpTKvA2oB8Nqey625CLN8bCN3TEbgx86Dsvr'
prv = '5K463ynhZoCDDa4RDcr63cUwWLTnKqmdcoTKTHBjqoKfv4u5V7p'

accounts_json = os.path.dirname(__file__)
accounts_json = os.path.join(accounts_json, '../../../..', 'tutorials/bios-boot-tutorial/accounts.json')

with open(accounts_json) as f:
    a = json.load(f)
    users = a['users']
    producers = a['producers']
    firstProducer = len(users)
    numProducers = len(producers)
    accounts = a['users'][:1000] + a['producers']

print(accounts[0])
print(len(accounts))

def create_accounts():
    step = 500
    for i in range(0, len(accounts), step):
        with producer:
            for j in range(step):
                if i+j >= len(accounts):
                    break
                a = accounts[i+j]
                print(a, i, j)
                if not eosapi.get_account(a['name']):
                    eosapi.create_account('eosio', a['name'], a['pub'], a['pub'])

def create_sys_account():
    with producer:
        for a in system_accounts:
            if not eosapi.get_account(a):
                eosapi.create_account('eosio', a, pub, pub)

def import_keys():
    keys = wallet.list_keys('mywallet', initeos.psw)
    for a in accounts:
        if not a['pub'] in keys:
            wallet.import_key('mywallet', a['pvt'], False)
    wallet.save('mywallet')

def allocate_funds():
    b = 0
    e = len(accounts)
    dist = numpy.random.pareto(1.161, e - b).tolist() # 1.161 = 80/20 rule
    dist.sort()
    dist.reverse()
    factor = 1_000_000_000 / sum(dist)
    total = 0
    for i in range(b, e):
        funds = round(factor * dist[i - b] * 10000)
        if i >= firstProducer and i < firstProducer + numProducers:
            funds = max(funds, round(args.min_producer_funds * 10000))
        total += funds
        accounts[i]['funds'] = funds
    return total

def int_to_currency(i):
    return '%d.%04d %s' % (i // 10000, i % 10000, 'EOS')


def create_tokens():

    msg = {"issuer":"eosio","maximum_supply":"10000000000.0000 EOS"}
    r, cost = eosapi.push_action('eosio.token', 'create', msg, {'eosio.token':'active'})
    assert r

    total_allocation = allocate_funds()

    r = eosapi.push_action('eosio.token','issue',{"to":"eosio","quantity":int_to_currency(total_allocation),"memo":""},{'eosio':'active'})
    assert r

def set_sys_contract():
    if not eosapi.get_code('eosio')[0]:
        contracts_path = os.path.join(os.getcwd(), '..', 'contracts', 'eosio.system', 'eosio.system')
        wast = contracts_path + '.wast'
        abi = contracts_path + '.abi'
        r = eosapi.set_contract('eosio', wast, abi, 0)
        assert r and not r['except']

    r = eosapi.push_action('eosio','setpriv',{'account':'eosio.msig', 'is_priv':1},{'eosio':'active'})
    assert r

def create_buyram():
    args = {"payer": 'eosio', "receiver":'hello', "quant":"0.1000 EOS"}
    r = eosapi.push_action('eosio','buyram', args,{'eosio':'active'})
    print(r)

def create_buyrambytes():
    args = {"payer": 'eosio', "receiver": 'hello', "bytes": 1024*1024*1024}
    r = eosapi.push_action('eosio','buyrambytes', args,{'eosio':'active'})
    print(r)

def create_staked_accounts(b, e):
    b, e = 0, len(accounts)
    args = object()
    args.ram_funds = 0.1
    args.min_stake = 0.9
    args.max_unstaked = 10
    
    ramFunds = round(args.ram_funds * 10000)
    configuredMinStake = round(args.min_stake * 10000)
    maxUnstaked = round(args.max_unstaked * 10000)
    for i in range(b, e):
        a = accounts[i]
        funds = a['funds']
        print('#' * 80)
        print('# %d/%d %s %s' % (i, e, a['name'], intToCurrency(funds)))
        print('#' * 80)
        if funds < ramFunds:
            print('skipping %s: not enough funds to cover ram' % a['name'])
            continue
        minStake = min(funds - ramFunds, configuredMinStake)
        unstaked = min(funds - ramFunds - minStake, maxUnstaked)
        stake = funds - ramFunds - unstaked
        stakeNet = round(stake / 2)
        stakeCpu = stake - stakeNet
        print('%s: total funds=%s, ram=%s, net=%s, cpu=%s, unstaked=%s' % (a['name'], intToCurrency(a['funds']), intToCurrency(ramFunds), intToCurrency(stakeNet), intToCurrency(stakeCpu), intToCurrency(unstaked)))
        assert(funds == ramFunds + stakeNet + stakeCpu + unstaked)
        
        retry(args.cleos + 'system newaccount --transfer eosio %s %s --stake-net "%s" --stake-cpu "%s" --buy-ram "%s"   ' % 
            (a['name'], a['pub'], intToCurrency(stakeNet), intToCurrency(stakeCpu), intToCurrency(ramFunds)))
        if unstaked:
            retry(args.cleos + 'transfer eosio %s "%s"' % (a['name'], intToCurrency(unstaked)))

def all():
    create_accounts()
    create_sys_account()
    import_keys()
    allocate_funds()
    create_tokens()
    set_sys_contract()
    
