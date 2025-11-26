from config import get_config

def main():
    print("Starting the program...")
    config = get_config()
    print("Configuration loaded successfully.")
    print(f"Sim mode: {config.sim_mode}")
    # Add your main logic here

if __name__ == "__main__":
    main()
