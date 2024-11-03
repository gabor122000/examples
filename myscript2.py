# ==============================================================================
# -- find carla module ---------------------------------------------------------
# ==============================================================================


import glob
import os
import sys

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass


# ==============================================================================
# -- imports -------------------------------------------------------------------
# ==============================================================================

import carla
import random
import time
import threading
from collections import deque

# Connect to the CARLA server
client = carla.Client('localhost', 2000)
client.set_timeout(10.0)
world = client.get_world()
blueprint_library = world.get_blueprint_library()

# Clear all actors to start fresh
for actor in world.get_actors():
    actor.destroy()

# Load a map with intersections, e.g., Town03
client.load_world('Town03')
time.sleep(2)  # Give the world time to load

# Set up the spectator view for monitoring
spectator = world.get_spectator()
spectator_transform = carla.Transform(
    carla.Location(x=0, y=0, z=30),
    carla.Rotation(pitch=-90)
)
spectator.set_transform(spectator_transform)

# Set up spectator to monitor the crossing from above
def set_spectator_view(world, location, height=300, pitch=-90):
    """
    Position the spectator camera above the intersection.
    
    :param world: The CARLA world object.
    :param location: The location at the center of the intersection.
    :param height: Height above the intersection for the view.
    :param pitch: Downward tilt of the spectator camera.
    """
    spectator = world.get_spectator()
    spectator_transform = carla.Transform(
        carla.Location(x=location.x, y=location.y, z=height),
        carla.Rotation(pitch=pitch)
    )
    spectator.set_transform(spectator_transform)
    print("Spectator view set at intersection.")

# Define the center of the intersection (adjust to your crossing's location)
intersection_center = carla.Location(x=0, y=0, z=0)  # Replace with actual coordinates if known
set_spectator_view(world, intersection_center)

# Now continue with the rest of your simulation setup...



# Define spawn points in each direction (North, South, East, West)
spawn_points = world.get_map().get_spawn_points()
north_spawn = random.choice([sp for sp in spawn_points if sp.location.y > 0])
south_spawn = random.choice([sp for sp in spawn_points if sp.location.y < 0])
east_spawn = random.choice([sp for sp in spawn_points if sp.location.x > 0])
west_spawn = random.choice([sp for sp in spawn_points if sp.location.x < 0])

# Create queues to track cars waiting from each direction
queues = {
    "north": deque(),
    "south": deque(),
    "east": deque(),
    "west": deque()
}

# Helper function to spawn vehicles with larger random offsets and multiple spawn points
def safe_spawn_vehicle(blueprint, spawn_points, max_attempts=5, spawn_offset=5.0):
    """
    Try to spawn a vehicle at one of several spawn points.
    If there's a collision, try shifting the location within each spawn point.
    """
    for spawn_point in spawn_points:
        for attempt in range(max_attempts):
            try:
                # Try to spawn the vehicle at this spawn point
                vehicle = world.try_spawn_actor(blueprint, spawn_point)
                if vehicle is not None:
                    return vehicle  # Successful spawn, return the vehicle
            except RuntimeError as e:
                print(f"Spawn attempt {attempt + 1} failed due to collision: {e}")
                # Adjust the spawn point slightly to attempt again
                spawn_point.location.x += random.uniform(-spawn_offset, spawn_offset)
                spawn_point.location.y += random.uniform(-spawn_offset, spawn_offset)

    print("Failed to spawn vehicle after multiple attempts.")
    return None  # Return None if all attempts fail

# Adjusted list of spawn points by direction (choose several per direction)
north_spawns = [sp for sp in spawn_points if sp.location.y > 0]
south_spawns = [sp for sp in spawn_points if sp.location.y < 0]
east_spawns = [sp for sp in spawn_points if sp.location.x > 0]
west_spawns = [sp for sp in spawn_points if sp.location.x < 0]

# Spawn 5 cars from each direction and add them to the queues
directions = ["north", "south", "east", "west"]
num_cars_per_direction = 5

for direction in directions:
    for _ in range(num_cars_per_direction):
        vehicle_bp = random.choice(blueprint_library.filter('vehicle.*'))
        
        # Use the helper function to safely spawn vehicles in each direction
        if direction == "north":
            vehicle = safe_spawn_vehicle(vehicle_bp, north_spawns)
        elif direction == "south":
            vehicle = safe_spawn_vehicle(vehicle_bp, south_spawns)
        elif direction == "east":
            vehicle = safe_spawn_vehicle(vehicle_bp, east_spawns)
        elif direction == "west":
            vehicle = safe_spawn_vehicle(vehicle_bp, west_spawns)
        
        if vehicle is not None:
            vehicle.set_autopilot(True)
            queues[direction].append(vehicle)
        else:
            print(f"Failed to spawn a vehicle in the {direction} direction.")



# Function to control traffic lights based on car arrival order
def control_traffic_lights(queues, green_duration=5):
    traffic_lights = world.get_actors().filter("traffic.traffic_light")

    # Keep track of the last light direction that was green
    last_green = None
    
    while True:
        # Check which queue has the first vehicle waiting
        for direction, queue in queues.items():
            if queue:
                first_vehicle = queue[0]  # Get the first vehicle in the queue
                distance = first_vehicle.get_location().distance(traffic_lights[0].get_location())

                # If the vehicle is close enough to the crossing, grant green light
                if distance < 20:
                    # Set all traffic lights to red first
                    for light in traffic_lights:
                        light.set_state(carla.TrafficLightState.Red)

                    # Grant green light to the current direction
                    print(f"Setting traffic light to green for {direction}")
                    for light in traffic_lights:
                        if direction in light.get_transform().location:
                            light.set_state(carla.TrafficLightState.Green)

                    time.sleep(green_duration)  # Hold green for the set duration

                    # Remove the vehicle from the queue after it crosses
                    queue.popleft()
                    last_green = direction
                    break
        time.sleep(0.5)

# Run the traffic light control loop in a separate thread
light_control_thread = threading.Thread(target=control_traffic_lights, args=(queues,))
light_control_thread.start()

# Set up camera sensors to monitor traffic at the intersection
sensor_locations = [
    carla.Transform(carla.Location(x=north_spawn.location.x, y=north_spawn.location.y, z=10), carla.Rotation(pitch=-30)),
    carla.Transform(carla.Location(x=south_spawn.location.x, y=south_spawn.location.y, z=10), carla.Rotation(pitch=-30)),
    carla.Transform(carla.Location(x=east_spawn.location.x, y=east_spawn.location.y, z=10), carla.Rotation(pitch=-30)),
    carla.Transform(carla.Location(x=west_spawn.location.x, y=west_spawn.location.y, z=10), carla.Rotation(pitch=-30))
]

sensors = []
for i, sensor_location in enumerate(sensor_locations):
    camera_bp = blueprint_library.find('sensor.camera.rgb')
    camera_bp.set_attribute('image_size_x', '800')
    camera_bp.set_attribute('image_size_y', '600')
    camera_bp.set_attribute('fov', '90')
    camera = world.spawn_actor(camera_bp, sensor_location)
    camera.listen(lambda image: image.save_to_disk(f'_out/crossing_{i}_%06d.png' % image.frame))
    sensors.append(camera)
    print(f"Camera {i} placed at {sensor_location.location}")

# Run the simulation for a set time
simulation_duration = 60  # seconds
print("Starting simulation for 60 seconds")
time.sleep(simulation_duration)

# Clean up actors
for sensor in sensors:
    sensor.stop()
    sensor.destroy()

for direction in directions:
    for vehicle in queues[direction]:
        vehicle.destroy()

light_control_thread.join()  # Ensure the traffic light thread ends cleanly
print("Simulation ended and cleanup completed.")
