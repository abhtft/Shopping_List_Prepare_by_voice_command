import pkg_resources

def check_each_package(file_path="requirements.txt"):
    print("Checking packages from requirements.txt...\n")
    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        package = line.strip()
        if not package or package.startswith('#'):
            continue  # Skip blank or commented lines
        try:
            requirement = pkg_resources.Requirement.parse(package)
            dist = pkg_resources.get_distribution(requirement.project_name)
            if dist not in requirement:
                print(f"⚠️ Version conflict: Required {package}, Installed {dist.version}")
            else:
                print(f"✅ Installed: {requirement.project_name}=={dist.version}")
        except pkg_resources.DistributionNotFound:
            print(f"❌ Not installed: {package}")
        except pkg_resources.VersionConflict as e:
            print(f"⚠️ Version conflict: {e.report()}")

# Example usage
check_each_package()

#So yes — Python version influences what pip installs.