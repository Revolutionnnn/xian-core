import dao
import rewards
import stamp_cost
import currency

nodes = Variable()
votes = Hash(default_value=False) # votes[id] = {"yes": int, "no": int, type: str, arg: Any, "voters": list, "finalized": bool}
total_votes = Variable()
types = Variable()

registration_fee = Variable()
pending_registrations = Hash(default_value=False)
pending_leave = Hash(default_value=False)

@construct
def seed(genesis_nodes: list, genesis_registration_fee: int):
    nodes.set(genesis_nodes)
    types.set(["add_member", "remove_member", "change_registration_fee", "reward_change", "dao_payout", "stamp_cost_change", "change_types"])
    total_votes.set(0)
    registration_fee.set(genesis_registration_fee)

@export
def propose_vote(type_of_vote: str, arg: Any):
    assert ctx.caller in nodes.get(), "Only nodes can propose new votes"

    if type_of_vote == "add_member":
        assert pending_registrations[arg] == True, "Member must have pending registration"
    
    assert type_of_vote in types.get(), "Invalid type"
    proposal_id = total_votes.get() + 1
    votes[proposal_id] = {"yes": 0, "no": 0, "type": type_of_vote, "arg": arg, "voters": [ctx.caller], "finalized": False}
    total_votes.set(proposal_id)
    return proposal_id

@export
def vote(proposal_id: int, vote: str):
    assert ctx.caller in nodes.get(), "Only nodes can vote"
    assert votes[proposal_id], "Invalid proposal"
    assert votes[proposal_id]["finalized"] == False, "Proposal already finalized"
    assert vote in ["yes", "no"], "Invalid vote"
    assert ctx.caller not in votes[proposal_id]["voters"], "Already voted"

    # Do this because we can't modify a dict in a hash without reassigning it
    cur_vote = votes[proposal_id]
    cur_vote[vote] += 1
    cur_vote["voters"].append(ctx.caller)
    votes[proposal_id] = cur_vote

    if votes[proposal_id]["voters"] >= len(nodes.get()) // 2:
        if not votes[proposal_id]["finalized"]:
            finalize_vote(proposal_id)

    return cur_vote


def finalize_vote(proposal_id: int):
    cur_vote = votes[proposal_id]

    # Check if majority yes
    if cur_vote["yes"] > cur_vote["no"]:
        if cur_vote["type"] == "add_member":
            nodes.set(nodes.get() + [cur_vote["arg"]])
        elif cur_vote["type"] == "remove_member":
            nodes.set([node for node in nodes.get() if node != cur_vote["arg"]])
        elif cur_vote["type"] == "reward_change":
            rewards.set_value(new_value=cur_vote["arg"])
        elif cur_vote["type"] == "dao_payout":
            currency.transfer_from_dao(args=cur_vote["arg"])
        elif cur_vote["type"] == "stamp_cost_change":
            stamp_cost.set_value(new_value=cur_vote["arg"])
        elif cur_vote["type"] == "change_registration_fee":
            registration_fee.set(cur_vote["arg"])
        elif cur_vote["type"] == "change_types":
            types.set(cur_vote["arg"])
    
    cur_vote["finalized"] = True

    votes[proposal_id] = cur_vote
    return cur_vote

@export
def announce_leave():
    assert ctx.caller in nodes.get(), "Not a node"
    assert pending_leave[ctx.caller] == False, "Already pending leave"
    pending_leave[ctx.caller] = now + datetime.timedelta(days=7)
    
@export
def leave():
    assert ctx.caller in nodes.get(), "Not a node"
    assert pending_leave[ctx.caller] != False, "No pending leave"
    assert pending_leave[ctx.caller] < now, "Leave announcement period not over"
    nodes.set([node for node in nodes.get() if node != ctx.caller])
    pending_leave[ctx.caller] = False

@export
def register():
    assert ctx.caller not in nodes.get(), "Already a node"
    assert pending_registrations[ctx.caller] == False, "Already pending registration"
    currency.transfer_from(registration_fee.get(), ctx.caller, ctx.this)
    pending_registrations[ctx.caller, registration_fee.get()] = True

@export
def unregister():
    assert ctx.caller not in nodes.get(), "If you're a node already, you can't unregister. You need to leave or be removed."
    assert pending_registrations[ctx.caller] == True, "No pending registration"
    currency.transfer(pending_registrations[ctx.caller], ctx.caller)
    pending_registrations[ctx.caller] = False