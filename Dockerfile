FROM centos:centos5

MAINTAINER Ukang'a Dickson <ukanga@gmail.com>

RUN yum update
RUN yum groupinstall -y "Development tools"
RUN yum install -y zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel
RUN yum install -y wget
WORKDIR /usr/local/src
RUN wget https://www.python.org/ftp/python/2.7.8/Python-2.7.8.tgz && tar xzf Python-2.7.8.tgz
WORKDIR /usr/local/src/Python-2.7.8
RUN ./configure --prefix=/usr/local --enable-unicode=ucs4 --enable-shared LDFLAGS="-Wl,-rpath /usr/local/lib" && make && make altinstall
WORKDIR /usr/local/src
RUN wget --no-check-certificate https://pypi.python.org/packages/source/s/setuptools/setuptools-1.4.2.tar.gz && tar -xvf setuptools-1.4.2.tar.gz
WORKDIR /usr/local/src/setuptools-1.4.2
RUN python2.7 setup.py install
WORKDIR /usr/local/src
RUN yum install -y curl
RUN curl https://raw.githubusercontent.com/pypa/pip/master/contrib/get-pip.py | python2.7 -
# RUN wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py && python2.7 ez_setup.py && easy_install-2.7 pip
# RUN yum install -y wget
# RUN curl -O https://raw.githubusercontent.com/scalp42/python-2.7.x-on-Centos-5.x/master/install_python27.sh && chmod +x install_python27.sh && ./install_python27.sh
