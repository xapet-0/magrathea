#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int	picoshell(char **cmds[]);

static int	count_cmds(int argc, char **argv)
{
	int	ret = 1;

	for (int i = 1; i < argc; i++)
	{
		if (strcmp(argv[i], "|") == 0)
			ret++;
	}
	return (ret);
}

int	main(int argc, char **argv)
{
	if (argc < 2)
	{
		char *cmd1[] = {"echo", "squalala", NULL};
		char *cmd2[] = {"cat", NULL};
		char *cmd3[] = {"sed", "s/a/b/g", NULL};
		char **cmds[] = {cmd1, cmd2, cmd3, NULL};
		return (picoshell(cmds));
	}

	int		cmds_size = count_cmds(argc, argv);
	char	***cmds = calloc((size_t)(cmds_size + 1), sizeof(char **));
	if (!cmds)
	{
		fprintf(stderr, "Malloc error: %m\n");
		return (1);
	}

	int		i = 1;
	for (int cmd_i = 0; cmd_i < cmds_size; cmd_i++)
	{
		int len = 0;
		while (i + len < argc && strcmp(argv[i + len], "|") != 0)
			len++;
		cmds[cmd_i] = calloc((size_t)(len + 1), sizeof(char *));
		if (!cmds[cmd_i])
		{
			fprintf(stderr, "Malloc error: %m\n");
			return (1);
		}
		for (int j = 0; j < len; j++)
			cmds[cmd_i][j] = argv[i + j];
		cmds[cmd_i][len] = NULL;
		i += len + 1;
	}

	int ret = picoshell(cmds);
	for (int cmd_i = 0; cmd_i < cmds_size; cmd_i++)
		free(cmds[cmd_i]);
	free(cmds);
	return (ret);
}

