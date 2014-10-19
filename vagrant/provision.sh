echo bootstrapping cloudify-agent-packager...

# update and install prereqs
sudo apt-get -y update &&
sudo apt-get install -y curl python-dev rubygems rpm &&

# install fpm and configure gem/bundler
sudo gem install fpm --no-ri --no-rdoc &&
echo -e 'gem: --no-ri --no-rdoc\ninstall: --no-rdoc --no-ri\nupdate:  --no-rdoc --no-ri' >> ~/.gemrc

# install pip
curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python

# install virtualenv
sudo pip install virtualenv==1.11.4 &&

# install packman
pip install packman

# install agent-packager
pip install https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz

echo bootstrap done