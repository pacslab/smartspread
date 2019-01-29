#!/bin/bash
SERVER_IP="${SERVER_IP:-YOUR_SERVER_IP}"
SSH_USER="${SSH_USER:-$(echo $(whoami) | tr 'A-Z' 'a-z')}"
KEY_USER="${KEY_USER:-$(echo $(whoami) | tr 'A-Z' 'a-z')}"
RABBITMQ_ADMIN_PASS="${RABBITMQ_ADMIN_PASS:-YOUR_RABBITMQ_PASS}"

function preseed_staging() {
cat << EOF
STAGING SERVER (DIRECT VIRTUAL MACHINE) DIRECTIONS:
  1. Configure a static IP address directly on the VM
     su
     <enter password>
     nano /etc/network/interfaces
     [change the last line to look like this, remember to set the correct
      gateway for your router's IP address if it's not 192.168.1.1]
iface eth0 inet static
  address ${SERVER_IP}
  netmask 255.255.255.0
  gateway 192.168.1.1

  2. Reboot the VM and ensure the Debian CD is mounted

  3. Install sudo
     apt-get update && apt-get install -y -q sudo

  4. Add the user to the sudo group
     adduser ${SSH_USER} sudo

  5. Run the commands in: $0 --help
     Example:
       ./deploy.sh -a
EOF
}

function preseed_production() {
cat << EOF
  1. Adding the user:
    adduser ${KEY_USER}
  2. Add user to the group sudo:
    adduser ${KEY_USER} sudo
    gpasswd -a ${KEY_USER} sudo
  3. remove the need to enter a password:
    sudo passwd -d ${KEY_USER}
  4. Let the script do the rest, it will configure sudo, sudoers,
    add ssh keys, secure the ssh, etc.
    ./deploy.sh -a

EOF

read -n 1 -s -r -p "Press any key to continue"
echo "---"
configure_sudo
echo "---"
add_ssh_key
echo "---"
configure_secure_ssh
}

function configure_sudo () {
  echo "Configuring passwordless sudo..."
  scp "sudo/sudoers" "${SSH_USER}@${SERVER_IP}:/tmp/sudoers"
  ssh -t "${SSH_USER}@${SERVER_IP}" bash -c "'
sudo chmod 440 /tmp/sudoers
sudo chown root:root /tmp/sudoers
sudo mv /tmp/sudoers /etc
  '"
  echo "done!"
}


function add_ssh_key() {
  echo "Adding SSH key..."
  cat "$HOME/.ssh/id_rsa.pub" | ssh -t "${SSH_USER}@${SERVER_IP}" bash -c "'
mkdir /home/${KEY_USER}/.ssh
cat >> /home/${KEY_USER}/.ssh/authorized_keys
    '"
  ssh -t "${SSH_USER}@${SERVER_IP}" bash -c "'
chmod 700 /home/${KEY_USER}/.ssh
chmod 640 /home/${KEY_USER}/.ssh/authorized_keys
sudo chown ${KEY_USER}:${KEY_USER} -R /home/${KEY_USER}/.ssh
  '"
  echo "done!"
}

function configure_secure_ssh () {
  echo "Configuring secure SSH..."
  scp "ssh/sshd_config" "${SSH_USER}@${SERVER_IP}:/tmp/sshd_config"
  ssh -t "${SSH_USER}@${SERVER_IP}" bash -c "'
sudo chown root:root /tmp/sshd_config
sudo mv /tmp/sshd_config /etc/ssh
sudo systemctl restart ssh
  '"
  echo "done!"
}

function provision_server () {
  configure_sudo
  echo "###################################"
  add_ssh_key
  echo "###################################"
  configure_secure_ssh
  echo "###################################"
}

function install_rabbitmq () {
  ssh -t "${SSH_USER}@${SERVER_IP}" bash -c "'
sudo apt-get update
# enable rabitmq repository
echo "deb http://www.rabbitmq.com/debian/ testing main" | sudo tee --append /etc/apt/sources.list
curl http://www.rabbitmq.com/rabbitmq-signing-key-public.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get install -y rabbitmq-server
# To change configuration of rabitmq:
# sudo nano /etc/default/rabbitmq-server
# Enable management console:
sudo rabbitmq-plugins enable rabbitmq_management
# Allow management console:
sudo ufw allow 15672
# Allow the AMQP protocol:
sudo ufw allow 5672

# add permissions
sudo rabbitmqctl add_user admin ${RABBITMQ_ADMIN_PASS}
sudo rabbitmqctl set_user_tags admin administrator
sudo rabbitmqctl set_permissions -p / admin \".*\" \".*\" \".*\"

'"

  echo "You can now go to http://${SERVER_IP}:15672/"

  echo "
# To start the service:
sudo service rabbitmq-server start

# To stop the service:
sudo service rabbitmq-server stop

# To restart the service:
sudo service rabbitmq-server restart

# To check the status:
sudo service rabbitmq-server status
  "
}


function help_menu () {
cat << EOF
Usage: ${0} (-h | -S | -u | -k | -s | -d [docker_ver] | -a [docker_ver])

use these commands:
export SERVER_IP=10.12.7.20
export SSH_USER=ubuntu
export KEY_USER=ubuntu

ENVIRONMENT VARIABLES:
   SERVER_IP        IP address to work on, ie. staging or production
                    Defaulting to ${SERVER_IP}

   SSH_USER         User account to ssh and scp in as
                    Defaulting to ${SSH_USER}

   KEY_USER         User account linked to the SSH key
                    Defaulting to ${KEY_USER}

OPTIONS:
   -h|--help                 Show this message
   -S|--preseed-staging      Preseed intructions for the staging server
   -P|--preseed-production   Preseed intructions and commands for the production server
   -u|--sudo                 Configure passwordless sudo
   -k|--ssh-key              Add SSH key
   -s|--ssh                  Configure secure SSH
   -a|--all                  Provision everything except preseeding

EXAMPLES:
   Show preseed staging help info:
        $ deploy -S|--preseed-staging

   Show preseed production help info:
        $ deploy -P|--preseed-production

   Configure passwordless sudo:
        $ deploy -u|--sudo

   Add SSH key:
        $ deploy -k|--ssh-key

   Configure secure SSH:
        $ deploy -s|--ssh

   Configure secure SSH:
        $ deploy --install-rabitmq

   Configure everything together:
        $ deploy -a|--all
EOF
}


while [[ $# > 0 ]]
do
case "${1}" in
  -S|--preseed-staging)
  preseed_staging
  shift
  ;;
  -P|--preseed-production)
  preseed_production
  shift
  ;;
  -u|--sudo)
  configure_sudo
  shift
  ;;
  -k|--ssh-key)
  add_ssh_key
  shift
  ;;
  -s|--ssh)
  configure_secure_ssh
  shift
  ;;
  -a|--all)
  provision_server
  shift
  ;;
  --install-rabbitmq)
  install_rabbitmq
  shift
  ;;
  -h|--help)
  help_menu
  shift
  ;;
  *)
  echo "${1} is not a valid flag, try running: ${0} --help"
  ;;
esac
shift
done
