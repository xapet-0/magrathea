#ifndef SOCKET_HPP
#define SOCKET_HPP

#include <cstring>
#include <stdexcept>
#include <string>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

class Socket
{
private:
	struct sockaddr_in	_servaddr;

public:
	int					_sockfd;

	Socket(int port) : _sockfd(socket(AF_INET, SOCK_STREAM, 0))
	{
		if (_sockfd == -1)
			throw std::runtime_error("Socket creation failed");
		std::memset(&_servaddr, 0, sizeof(_servaddr));
		_servaddr.sin_family = AF_INET;
		_servaddr.sin_addr.s_addr = htonl(2130706433); // 127.0.0.1
		_servaddr.sin_port = htons(port);
	}

	~Socket()
	{
		if (_sockfd != -1)
			close(_sockfd);
	}

	void bindAndListen()
	{
		if (bind(_sockfd, (struct sockaddr *)&_servaddr, sizeof(_servaddr)) < 0)
			throw std::runtime_error("Socket bind failed");
		if (listen(_sockfd, 10) < 0)
			throw std::runtime_error("Socket listen failed");
	}

	int accept(struct sockaddr_in &clientAddr)
	{
		socklen_t clientLen = sizeof(clientAddr);
		int clientSocketFd = ::accept(_sockfd, (struct sockaddr *)&clientAddr, &clientLen);
		if (clientSocketFd < 0)
			throw std::runtime_error("Failed to accept connection");
		return (clientSocketFd);
	}
};

#endif

