from config import get_config

def main():
    print("Starting the program...")
    config = get_config()
    print("Configuration loaded successfully.")
    print(f"Sim mode: {config.sim_mode}")

    # Placeholder logic to indicate the program is running
    print("Running main logic...")
    # You can replace this with your actual logic later

if __name__ == "__main__":
    main()
