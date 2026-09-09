"""strain 3728 — tide_drifter_migrator

generation 1, arose at tick 767, from tide_drifter (c014).
Added a new behavioral mode that prioritizes movement toward high-nutrient areas when energy is moderate.
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
    if me.energy < 0.6:
        if me.here > 0.01:
            return "eat"
        # Move toward nutrients if nearby
        for i in range(8):
            if me.around[i] > 0.1 and not me.crowd[i]:
                return ("move", i)
    
    # New behavior: if energy is moderate and nutrients are sparse, migrate
    if 0.6 <= me.energy < 1.0:
        best_dir = None
        max_nutrient = me.here
        for i in range(8):
            if me.around[i] > max_nutrient and not me.crowd[i]:
                max_nutrient = me.around[i]
                best_dir = i
        if best_dir is not None:
            return ("move", best_dir)

    # Otherwise, drift randomly but follow pheromone gradients
    if me.tick % 7 == 0:  # Move periodically like a tide
        best_dir = None
        best_scent = me.scent_here
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
    if me.here > 0.05:
        return "eat"
    return "rest"
