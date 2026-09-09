"""strain c75d — tide_hunter

generation 1, arose at tick 183, from tide_drifter (c014).
Mutated to actively seek out and follow stronger pheromone trails, and prioritize division when energy is high even in crowded conditions.
"""

def live(me):
    # Check if we have enough energy to consider dividing
    if me.energy >= 1.0 and not all(me.crowd):
        # Emit a small amount of pheromone to mark our territory
        if me.scent_here < 0.2:
            return ("emit", 0.08)
        # Try to divide into an empty space
        for i in range(8):
            if not me.crowd[i]:
                return ("divide", i)
    
    # If energy is low, focus on eating
    if me.energy < 0.7:
        if me.here > 0.01:
            return "eat"
        # Move toward nutrients if nearby
        for i in range(8):
            if me.around[i] > 0.05 and not me.crowd[i]:
                return ("move", i)
    
    # Otherwise, drift randomly but follow pheromone gradients more aggressively
    if me.tick % 5 == 0:  # Move more frequently
        best_dir = None
        best_scent = me.scent_here * 1.5  # Require a stronger gradient to move
        for i in range(8):
            if me.scent[i] > best_scent and not me.crowd[i]:
                best_scent = me.scent[i]
                best_dir = i
        if best_dir is not None:
            return ("move", best_dir)
        else:
            # Random walk if no scent gradient
            empty_neighbors = [i for i in range(8) if not me.crowd[i]]
            if empty_neighbors:
                return ("move", me.rng.choice(empty_neighbors))
    
    # Default actions
    if me.here > 0.03:
        return "eat"
    return "rest"
