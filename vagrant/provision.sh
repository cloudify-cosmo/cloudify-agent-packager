echo bootstrapping cloudify-agent-packager...

# update and install prereqs
sudo apt-get -y update &&
sudo apt-get install -y curl python-dev rubygems rpm &&

# install ruby
wget ftp://ftp.ruby-lang.org/pub/ruby/1.9/ruby-1.9.3-p547.tar.bz2
tar -xjf ruby-1.9.3-p547.tar.bz2
cd ruby-1.9.3-p547
./configure --disable-install-doc
make
sudo make install
cd ~

# install fpm and configure gem/bundler
sudo gem install fpm --no-ri --no-rdoc &&
echo -e 'gem: --no-ri --no-rdoc\ninstall: --no-rdoc --no-ri\nupdate:  --no-rdoc --no-ri' >> ~/.gemrc

# install pip
curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python

# install virtualenv
sudo pip install virtualenv==1.11.4 &&

# install packman ?
# pip install packman

# install agent-packager
cd ~
virtualenv cfyap
source cfyap/bin/activate
pip install https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz

# create agent tar
cfy-ap -f -c ~/cloudify-agent-packager/config/config.yaml -v

DIST=$(python -c "import platform; print(platform.dist()[0])")

# get agent resources
mkdir
wget https://github.com/cloudify-cosmo/cloudify-packager/raw/master/package-configuration/ubuntu-agent/Ubuntu-agent-disable-requiretty.sh -O

# create agent deb
mkdir ~/cloudify-agent-packager/agents/
fpm -n ${DIST}-agent -s dir -t deb -v 3.1m5 -C ~/cloudify-agent-packager/agents/ -f

echo "source /home/vagrant/cfyap/bin/activate" >> /home/vagrant/.bashrc

echo bootstrap done