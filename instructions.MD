# Set the correct permissions
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

# Start the SSH agent
eval "$(ssh-agent -s)"

# Add your SSH key to the agent
ssh-add ~/.ssh/id_rsa

# Verify the SSH key is added
ssh-add -l

# Test SSH connection to GitHub
ssh -T git@github.com