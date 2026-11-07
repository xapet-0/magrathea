#include <unistd.h>
#include <sys/wait.h>
#include <string.h>
#include <stdlib.h>

static void	err(char *s)
{
	while (*s)
		write(2, s++, 1);
}

static int	cd(char **av, int i)
{
	if (i != 2)
		return (err("error: cd: bad arguments\n"), 1);
	if (chdir(av[1]) == -1)
		return (err("error: cd: cannot change directory to "), err(av[1]), err("\n"), 1);
	return (0);
}

static int	exec(char **av, int i, char **envp)
{
	int	fd[2];
	int	status;
	int	has_pipe = av[i] && !strcmp(av[i], "|");

	if (!has_pipe && !strcmp(*av, "cd"))
		return (cd(av, i));
	if (has_pipe && pipe(fd) == -1)
		return (err("error: fatal\n"), 1);
	int pid = fork();
	if (!pid)
	{
		av[i] = 0;
		if (has_pipe && (dup2(fd[1], 1) == -1 || close(fd[0]) == -1 || close(fd[1]) == -1))
			return (err("error: fatal\n"), 1);
		if (!strcmp(*av, "cd"))
			exit(cd(av, i));
		execve(*av, av, envp);
		err("error: cannot execute ");
		err(*av);
		err("\n");
		exit(1);
	}
	waitpid(pid, &status, 0);
	if (has_pipe && (dup2(fd[0], 0) == -1 || close(fd[0]) == -1 || close(fd[1]) == -1))
		return (err("error: fatal\n"), 1);
	return (WIFEXITED(status) && WEXITSTATUS(status));
}

int	main(int ac, char **av, char **envp)
{
	int	i = 0;
	int	status = 0;

	if (ac > 1)
	{
		while (av[i] && av[++i])
		{
			av += i;
			i = 0;
			while (av[i] && strcmp(av[i], "|") && strcmp(av[i], ";"))
				i++;
			if (i)
				status = exec(av, i, envp);
		}
	}
	return (status);
}
