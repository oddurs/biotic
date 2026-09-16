"""strain 50d2 — tide_drifter_kin

generation 1, arose at tick 588, from tide_drifter (c014).
Now considers kinship when moving toward scent, preferring to stay near related cells.
"""

def live(me):
    # Check if we have enough energy to consider dividing
    if me.energy >= 1.2 and not all(me.crowd):
        # Emit a small amount of pheromone to mark our territory
        if me.scent_here < 0.1:
            return ("emit", 0.05)
        # Try to divide into an empty space
        for i in range(8):
            if not me.crowd[i]:
                return ("divide", i)
    
    # If energy is low, focus on eating
    if me.energy < 0.8:
        if me.here > 0.01:
            return "eat"
        # Move toward nutrients if nearby
        for i in range(8):
            if me.around[i] > 0.1 and not me.crowd[i]:
                return ("move", i)
    
    # Otherwise, drift randomly but follow pheromone gradients
    if me.tick % 7 == 0:  # Move periodically like a tide
        best_dir = None
        best_scent = me.scent_here
        for i in range(8):
            if me.scent[i] > best_scent and not me.crowd[i]:
                if me.kin[i] or best_dir is None:
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
    if me.here > 0.05:
        return "eat"
    return "rest"
