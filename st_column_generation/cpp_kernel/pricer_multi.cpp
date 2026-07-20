// v3: one layered Dijkstra per query, GROUPED destination outputs.
// query : int32 n_e, (int32 node, float64 c0)*, int32 n_groups,
//         per group: int32 n_nodes, int32 nodes[]
// output: per group: float64 best_cost, int32 n_arcs, int64 arcs[]
// Groups are typically stations (their exit-node lists); the Python
// side maps station groups to destination zones via egress walks.

#include <cstdio>
#include <cstdint>
#include <vector>
#include <queue>
using namespace std;

int main(int argc, char** argv) {
    if (argc < 4) { fprintf(stderr, "usage: g q o\n"); return 1; }
    FILE* fg = fopen(argv[1], "rb");
    int32_t n_nodes, R; int64_t n_arcs; double rebate;
    fread(&n_nodes, 4, 1, fg); fread(&n_arcs, 8, 1, fg);
    fread(&R, 4, 1, fg); fread(&rebate, 8, 1, fg);
    vector<int64_t> off(n_nodes + 1);
    vector<int32_t> head(n_arcs);
    vector<double> cost(n_arcs);
    vector<int8_t> tag(n_arcs);
    fread(off.data(), 8, n_nodes + 1, fg);
    fread(head.data(), 4, n_arcs, fg);
    fread(cost.data(), 8, n_arcs, fg);
    fread(tag.data(), 1, n_arcs, fg);
    fclose(fg);

    const double INF = 1e18;
    int64_t NS = (int64_t)(R + 1) * n_nodes;
    vector<double> dist(NS, INF);
    vector<int32_t> stamp(NS, -1);
    vector<int64_t> pred_arc(NS, -1), pred_st(NS, -1);
    typedef pair<double, int64_t> PQ;
    priority_queue<PQ, vector<PQ>, greater<PQ>> pq;

    FILE* fq = fopen(argv[2], "rb");
    FILE* fo = fopen(argv[3], "wb");
    int32_t n_q; fread(&n_q, 4, 1, fq);
    for (int32_t q = 0; q < n_q; q++) {
        int32_t n_e; fread(&n_e, 4, 1, fq);
        while (!pq.empty()) pq.pop();
        for (int32_t i = 0; i < n_e; i++) {
            int32_t node; double c0;
            fread(&node, 4, 1, fq); fread(&c0, 8, 1, fq);
            int64_t s = node;
            if (stamp[s] != q || c0 < dist[s]) {
                dist[s] = c0; stamp[s] = q;
                pred_arc[s] = -1; pred_st[s] = -1;
                pq.push({c0, s});
            }
        }
        while (!pq.empty()) {
            auto [c, s] = pq.top(); pq.pop();
            if (stamp[s] != q || c > dist[s]) continue;
            int32_t u = (int32_t)(s % n_nodes);
            int32_t b = (int32_t)(s / n_nodes);
            for (int64_t a = off[u]; a < off[u + 1]; a++) {
                int32_t b2 = b; double w = cost[a];
                if (tag[a] == 1) {
                    if (b + 1 > R) continue;
                    b2 = b + 1;
                    if (b == 0) w -= rebate;
                }
                int64_t s2 = (int64_t)b2 * n_nodes + head[a];
                double nc = c + w;
                if (stamp[s2] != q || nc < dist[s2] - 1e-15) {
                    dist[s2] = nc; stamp[s2] = q;
                    pred_arc[s2] = a; pred_st[s2] = s;
                    pq.push({nc, s2});
                }
            }
        }
        int32_t n_g; fread(&n_g, 4, 1, fq);
        for (int32_t gi = 0; gi < n_g; gi++) {
            int32_t nn; fread(&nn, 4, 1, fq);
            double best = INF; int64_t best_s = -1;
            for (int32_t i = 0; i < nn; i++) {
                int32_t d; fread(&d, 4, 1, fq);
                for (int32_t b = 0; b <= R; b++) {
                    int64_t s = (int64_t)b * n_nodes + d;
                    if (stamp[s] == q && dist[s] < best) {
                        best = dist[s]; best_s = s;
                    }
                }
            }
            fwrite(&best, 8, 1, fo);
            vector<int64_t> path;
            if (best_s >= 0)
                for (int64_t s = best_s; pred_arc[s] >= 0;
                     s = pred_st[s])
                    path.push_back(pred_arc[s]);
            int32_t np = (int32_t)path.size();
            fwrite(&np, 4, 1, fo);
            for (int32_t i = np - 1; i >= 0; i--)
                fwrite(&path[i], 8, 1, fo);
        }
    }
    fclose(fq); fclose(fo);
    return 0;
}
