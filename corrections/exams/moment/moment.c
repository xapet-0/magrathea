#include <stdlib.h>

static int ft_strlen(const char *s)
{
	int i = 0;
	while (s[i])
		i++;
	return i;
}

static char *ft_strdup(const char *s)
{
	int len = ft_strlen(s);
	char *res = (char *)malloc(len + 1);
	int i = 0;
	if (!res)
		return NULL;
	while (s[i])
	{
		res[i] = s[i];
		i++;
	}
	res[i] = '\0';
	return res;
}

static unsigned int ft_uintlen(unsigned int nb)
{
	unsigned int i = 0;
	if (nb == 0)
		return 1;
	while (nb > 0)
	{
		nb /= 10;
		i++;
	}
	return i;
}

static char *ft_strcat_free(char *s1, const char *s2)
{
	int l1 = ft_strlen(s1);
	int l2 = ft_strlen(s2);
	char *res = (char *)malloc(l1 + l2 + 1);
	int i = 0, j = 0;
	if (!res)
	{
		free(s1);
		return NULL;
	}
	while (s1[i])
	{
		res[j++] = s1[i++];
	}
	i = 0;
	while (s2[i])
	{
		res[j++] = s2[i++];
	}
	res[j] = '\0';
	free(s1);
	return res;
}

static char *ft_utoa(unsigned int nb)
{
	int len = ft_uintlen(nb);
	char *tab = (char *)malloc(len + 1);
	if (!tab)
		return NULL;
	tab[len] = '\0';
	if (nb == 0)
	{
		tab[0] = '0';
		return tab;
	}
	while (nb != 0)
	{
		tab[--len] = (nb % 10) + '0';
		nb /= 10;
	}
	return tab;
}

char *moment(unsigned int duration)
{
	if (duration == 0)
		return ft_strdup("0 seconds ago.");
	else if (duration == 1)
		return ft_strdup("1 second ago.");
	else if (duration < 60)
		return ft_strcat_free(ft_utoa(duration), " seconds ago.");
	else if (duration < 120)
		return ft_strdup("1 minute ago.");
	else if (duration < 3600)
		return ft_strcat_free(ft_utoa(duration / 60), " minutes ago.");
	else if (duration < 7200)
		return ft_strdup("1 hour ago.");
	else if (duration < 86400)
		return ft_strcat_free(ft_utoa(duration / 3600), " hours ago.");
	else if (duration < 172800)
		return ft_strdup("1 day ago.");
	else if (duration < 2592000)
		return ft_strcat_free(ft_utoa(duration / 86400), " days ago.");
	else if (duration < 5184000)
		return ft_strdup("1 month ago.");
	else
		return ft_strcat_free(ft_utoa(duration / 2592000), " months ago.");
}
