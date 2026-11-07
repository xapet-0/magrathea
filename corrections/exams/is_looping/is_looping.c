struct s_node { int value; struct s_node *next; };

int is_looping(struct s_node *node)
{
    struct s_node *s = node, *f = node;
    while (f && f->next) {
        s = s->next;
        f = f->next->next;
        if (s == f) return 1;
    }
    return 0;
}
