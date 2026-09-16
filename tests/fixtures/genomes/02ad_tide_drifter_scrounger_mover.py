"""strain 02ad — tide_drifter_scrounger_mover

generation 2, arose at tick 903, from tide_drifter_scrounger (552b).
Increased movement frequency and lowered energy thresholds for eating and division.
"""

def live(me):
    # Check if we have enough energy to consider dividing
    if me.energy >= 1.0 and not all(me.crowd):
        # Try to divide into an empty space
        for i in range(8):
            if not me.crowd[i]:
                return ("divide", i)
    
    # If energy is low, focus on eating
    if me.energy < 0.9:
        if me.here > 0.01:
            return "eat"
        # Move toward nutrients if nearby
        for i in range(8):
            if me.around[i] > 0.05 and not me.crowd[i]:
                return ("move", i)
    
    # Otherwise, drift randomly
    if me.tick % 3 == 0:  # Move more frequently
        # Move towards food instead of scent
        best_dir = None
        best_food = me.here
        for i in range(8):
            if me.around[i] > best_food and not me.crowd[i]:
                best_food = me.around[i]
                best_dir = i
        if best_dir is not None:
            return ("move", best_dir)
        else:
            # Random walk
            empty_neighbors = [i for i in range(8) if not me.crowd[i]]
            if empty_neighbors:
                return ("move", me.rng.choice(empty_neighbors))
    
    # Default actions
    if me.here > 0.02:  # Lower threshold for eating
        return "eat"
    return "rest"
