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

# ==============================================================================
# -- world -------------------------------------------------------------------
# ==============================================================================

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

# Get a list of traffic light actors and identify the ones near the crossing
traffic_lights = world.get_actors().filter("traffic.traffic_light")

# Choose a random intersection to set up a crossing
spawn_points = world.get_map().get_spawn_points()
crossing_spawn_point = random.choice(spawn_points)
crossing_location = crossing_spawn_point.location

# Set up a spectator view
spectator = world.get_spectator()
spectator_transform = carla.Transform(
    carla.Location(x=crossing_location.x, y=crossing_location.y - 20, z=20),
    carla.Rotation(pitch=-30)
)
spectator.set_transform(spectator_transform)
print("Spectator view set at the crossing.")

# Spawn sensors at each corner of the intersection
sensor_locations = [
    carla.Transform(carla.Location(x=crossing_location.x + 10, y=crossing_location.y, z=10), carla.Rotation(pitch=-30)),
    carla.Transform(carla.Location(x=crossing_location.x - 10, y=crossing_location.y, z=10), carla.Rotation(pitch=-30)),
    carla.Transform(carla.Location(x=crossing_location.x, y=crossing_location.y + 10, z=10), carla.Rotation(pitch=-30)),
    carla.Transform(carla.Location(x=crossing_location.x, y=crossing_location.y - 10, z=10), carla.Rotation(pitch=-30))
]

# Initialize sensors (camera or lidar) in each direction
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

# Function to control traffic light states (alternate red/green)
def control_traffic_lights(lights, green_duration=10, red_duration=5):
    while True:
        for light in lights:
            light.set_state(carla.TrafficLightState.Green)
        print("Traffic lights are Green")
        time.sleep(green_duration)
        
        for light in lights:
            light.set_state(carla.TrafficLightState.Red)
        print("Traffic lights are Red")
        time.sleep(red_duration)

# Run the traffic light control loop in a separate thread
light_control_thread = threading.Thread(target=control_traffic_lights, args=(traffic_lights,))
light_control_thread.start()

# Spawn random vehicles at some spawn points
num_vehicles = 40
for _ in range(num_vehicles):
    vehicle_bp = random.choice(blueprint_library.filter('vehicle.*'))
    spawn_point = random.choice(spawn_points)
    vehicle = world.spawn_actor(vehicle_bp, spawn_point)
    vehicle.set_autopilot(True)

# Run the simulation for a set time
simulation_duration = 60  # seconds
print("Starting simulation for 60 seconds")
time.sleep(simulation_duration)

# Clean up actors
for sensor in sensors:
    sensor.stop()
    sensor.destroy()

for vehicle in world.get_actors().filter('vehicle.*'):
    vehicle.destroy()

light_control_thread.join()  # Ensure the traffic light thread ends cleanly
print("Simulation ended and cleanup completed.")
