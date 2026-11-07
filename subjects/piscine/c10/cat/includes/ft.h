/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft.h                                               :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/11 12:12:51 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/15 03:43:50 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#ifndef FT_H
# define FT_H

# define __BUFF 30000

# include <fcntl.h>
# include <unistd.h>
# include <sys/stat.h>
# include <sys/types.h>
# include <errno.h>
# include <string.h>
# include <libgen.h>

void	ft_putchar(char c, int out);
void	ft_swap(int *a, int *b);
void	ft_putstr(char *str, int out);
void	ft_putstr_buf(char *str, int size);
int		ft_strlen(char *str);
int		ft_strcmp(char *s1, char *s2);
int		ft_file_read(char *filepath);

void	no_args(char **argv);

#endif
