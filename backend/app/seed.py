from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import (
    Assessment,
    AssessmentProblem,
    Contest,
    ContestProblem,
    HintChunk,
    Problem,
    TestCase,
    User,
)


def _p(db, **kwargs) -> Problem:
    existing = db.query(Problem).filter(Problem.slug == kwargs["slug"]).first()
    if existing:
        return existing
    p = Problem(**kwargs)
    db.add(p)
    db.flush()
    return p


def _tc(db, problem_id, input_data, expected_output, is_sample=False, points=10, order_index=0):
    db.add(
        TestCase(
            problem_id=problem_id,
            input_data=input_data,
            expected_output=expected_output,
            is_sample=is_sample,
            points=points,
            order_index=order_index,
        )
    )


def seed_if_empty(db: Session) -> None:
    if db.query(User).first():
        return

    admin = User(
        username="admin",
        email="admin@aether.dev",
        hashed_password=hash_password("admin123"),
        is_admin=True,
        rating=2100,
    )
    demo = User(
        username="demo",
        email="demo@aether.dev",
        hashed_password=hash_password("demo123"),
        is_admin=False,
        rating=1640,
    )
    db.add_all([admin, demo])
    db.flush()

    two_sum = _p(
        db,
        slug="two-sum",
        title="Two Sum",
        difficulty="Easy",
        tags="array,hashmap",
        time_limit_ms=2000,
        memory_limit_mb=256,
        statement=(
            "Given an array of integers `nums` and an integer `target`, return the indices of the two numbers "
            "such that they add up to `target`.\n\n"
            "You may assume that each input has exactly one solution, and you may not use the same element twice.\n\n"
            "Return the indices in ascending order, space-separated on a single line.\n\n"
            "**Input**\n"
            "- First line: integer `n` (2 ≤ n ≤ 10^4)\n"
            "- Second line: `n` integers `nums[i]` (−10^9 ≤ nums[i] ≤ 10^9)\n"
            "- Third line: integer `target`"
        ),
        input_spec="n, then n integers, then target",
        output_spec="Two indices, 0-based, ascending, space-separated",
        constraints="Exactly one valid pair exists.",
        starter_python=(
            "n = int(input())\n"
            "nums = list(map(int, input().split()))\n"
            "target = int(input())\n"
            "\n"
            "# write your solution\n"
            "print(0, 1)\n"
        ),
        starter_cpp=(
            "#include <bits/stdc++.h>\nusing namespace std;\nint main(){\n"
            "  ios::sync_with_stdio(false); cin.tie(nullptr);\n"
            "  int n; cin >> n; vector<int> a(n); for(int& x: a) cin >> x;\n"
            "  int t; cin >> t;\n  cout << 0 << ' ' << 1 << '\\n';\n}\n"
        ),
        starter_java=(
            "import java.util.*;\npublic class Main {\n  public static void main(String[] args) {\n"
            "    Scanner sc = new Scanner(System.in);\n    int n = sc.nextInt();\n"
            "    int[] a = new int[n];\n    for (int i = 0; i < n; i++) a[i] = sc.nextInt();\n"
            "    int t = sc.nextInt();\n    System.out.println(\"0 1\");\n  }\n}\n"
        ),
        hint="A hashmap from value to index turns the inner search into O(1).",
        editorial="Scan left to right. For each x, look up target-x. If present, emit indices. Else store x.",
    )
    _tc(db, two_sum.id, "4\n2 7 11 15\n9\n", "0 1\n", True, 10, 0)
    _tc(db, two_sum.id, "3\n3 2 4\n6\n", "1 2\n", True, 10, 1)
    _tc(db, two_sum.id, "2\n3 3\n6\n", "0 1\n", False, 20, 2)
    _tc(db, two_sum.id, "5\n-1 -2 -3 -4 -5\n-8\n", "2 4\n", False, 20, 3)
    db.add_all(
        [
            HintChunk(problem_id=two_sum.id, content="Brute force checks every pair in O(n^2). Too slow at n=1e4.", level=1),
            HintChunk(problem_id=two_sum.id, content="Store seen values in a map. For x, query target-x.", level=2),
            HintChunk(problem_id=two_sum.id, content="Return indices in ascending order.", level=3),
        ]
    )

    pal = _p(
        db,
        slug="valid-palindrome",
        title="Valid Palindrome",
        difficulty="Easy",
        tags="string,two-pointers",
        statement=(
            "A phrase is a palindrome if, after converting all uppercase letters into lowercase and removing "
            "all non-alphanumeric characters, it reads the same forward and backward.\n\n"
            "Given a string `s` on a single line, print `YES` if it is a palindrome, otherwise `NO`."
        ),
        input_spec="One line of text",
        output_spec="YES or NO",
        constraints="1 ≤ |s| ≤ 2·10^5",
        starter_python="s = input()\nprint('YES')\n",
        starter_cpp="#include <bits/stdc++.h>\nusing namespace std; int main(){ string s; getline(cin,s); cout<<\"YES\\n\"; }\n",
        starter_java="import java.util.*;\npublic class Main { public static void main(String[] a){ System.out.println(\"YES\"); } }\n",
        hint="Two pointers skipping non-alphanumeric characters.",
        editorial="Normalize to lowercase alphanumerics, then two-pointer compare.",
    )
    _tc(db, pal.id, "A man, a plan, a canal: Panama\n", "YES\n", True, 10, 0)
    _tc(db, pal.id, "race a car\n", "NO\n", True, 10, 1)
    _tc(db, pal.id, " \n", "YES\n", False, 15, 2)
    _tc(db, pal.id, "0P\n", "NO\n", False, 15, 3)

    climb = _p(
        db,
        slug="climbing-stairs",
        title="Climbing Stairs",
        difficulty="Easy",
        tags="dp,math",
        statement=(
            "You are climbing a staircase. It takes `n` steps to reach the top. Each time you can climb 1 or 2 steps. "
            "In how many distinct ways can you climb to the top?\n\n"
            "Input: a single integer n (1 ≤ n ≤ 45).\nOutput: a single integer."
        ),
        input_spec="One integer n",
        output_spec="Number of ways",
        constraints="1 ≤ n ≤ 45",
        starter_python="n = int(input())\nprint(0)\n",
        starter_cpp="#include <bits/stdc++.h>\nusing namespace std; int main(){ int n; cin>>n; cout<<0; }\n",
        starter_java="import java.util.*;\npublic class Main { public static void main(String[] a){ System.out.println(0); } }\n",
        hint="This is Fibonacci. f(n) = f(n-1) + f(n-2).",
        editorial="DP: dp[i] = dp[i-1] + dp[i-2] with dp[1]=1, dp[2]=2.",
    )
    _tc(db, climb.id, "2\n", "2\n", True, 10, 0)
    _tc(db, climb.id, "3\n", "3\n", True, 10, 1)
    _tc(db, climb.id, "1\n", "1\n", False, 10, 2)
    _tc(db, climb.id, "10\n", "89\n", False, 20, 3)
    _tc(db, climb.id, "45\n", "1836311903\n", False, 30, 4)

    isl = _p(
        db,
        slug="number-of-islands",
        title="Number of Islands",
        difficulty="Medium",
        tags="graph,dfs,bfs,grid",
        statement=(
            "Given a grid of `'1'`s (land) and `'0'`s (water), count the number of islands. "
            "An island is surrounded by water and is formed by connecting adjacent lands horizontally or vertically.\n\n"
            "**Input**\n- First line: `m n`\n- Next `m` lines: strings of length `n` consisting of 0/1."
        ),
        input_spec="m n then m binary strings",
        output_spec="Integer count",
        constraints="1 ≤ m, n ≤ 300",
        starter_python="m, n = map(int, input().split())\ngrid = [input().strip() for _ in range(m)]\nprint(0)\n",
        starter_cpp="#include <bits/stdc++.h>\nusing namespace std; int main(){ int m,n; cin>>m>>n; cout<<0; }\n",
        starter_java="import java.util.*;\npublic class Main { public static void main(String[] a){ System.out.println(0); } }\n",
        hint="DFS or BFS from every unvisited land cell, flood-fill, increment once per component.",
        editorial="Iterate cells. On a '1' not visited, BFS/DFS the component and mark visited.",
    )
    _tc(db, isl.id, "4 5\n11110\n11010\n11000\n00000\n", "1\n", True, 15, 0)
    _tc(db, isl.id, "4 5\n11000\n11000\n00100\n00011\n", "3\n", True, 15, 1)
    _tc(db, isl.id, "1 1\n0\n", "0\n", False, 10, 2)
    _tc(db, isl.id, "1 1\n1\n", "1\n", False, 10, 3)

    lru = _p(
        db,
        slug="lru-cache-ops",
        title="LRU Hit Counter",
        difficulty="Medium",
        tags="design,hashmap,linked-list",
        statement=(
            "Simulate an LRU cache of capacity `c`. Process `q` operations.\n"
            "- `PUT k v` — insert / update key k with value v\n"
            "- `GET k` — print the value, or -1 if missing\n\n"
            "Each GET that hits should still count as a use (move to most recently used).\n\n"
            "**Input**\nFirst line: `c q`\nNext q lines: operations."
        ),
        input_spec="capacity, queries, then operations",
        output_spec="One line per GET",
        constraints="1 ≤ c,q ≤ 2000",
        starter_python="c, q = map(int, input().split())\nfor _ in range(q):\n    parts = input().split()\n",
        starter_cpp="#include <bits/stdc++.h>\nusing namespace std; int main(){ int c,q; cin>>c>>q; }\n",
        starter_java="import java.util.*;\npublic class Main { public static void main(String[] a){} }\n",
        hint="Hash map + doubly linked list, or OrderedDict.",
        editorial="Python: collections.OrderedDict. move_to_end on get/put. popitem(last=False) on eviction.",
    )
    _tc(
        db,
        lru.id,
        "2 6\nPUT 1 1\nPUT 2 2\nGET 1\nPUT 3 3\nGET 2\nGET 3\n",
        "1\n-1\n3\n",
        True,
        20,
        0,
    )
    _tc(
        db,
        lru.id,
        "1 4\nPUT 1 10\nGET 1\nPUT 2 20\nGET 1\n",
        "10\n-1\n",
        False,
        20,
        1,
    )

    kth = _p(
        db,
        slug="kth-largest",
        title="Kth Largest Element",
        difficulty="Medium",
        tags="heap,sorting",
        statement=(
            "Given an integer array `nums` and an integer `k`, return the kth largest element in the array. "
            "Note that it is the kth largest element in sorted order, not the kth distinct element.\n\n"
            "**Input**\n- Line 1: n k\n- Line 2: n integers"
        ),
        input_spec="n k then n integers",
        output_spec="One integer",
        constraints="1 ≤ k ≤ n ≤ 10^5, |ai| ≤ 10^4",
        starter_python="n, k = map(int, input().split())\nnums = list(map(int, input().split()))\nprint(0)\n",
        starter_cpp="#include <bits/stdc++.h>\nusing namespace std; int main(){ int n,k; cin>>n>>k; cout<<0; }\n",
        starter_java="import java.util.*;\npublic class Main { public static void main(String[] a){ System.out.println(0); } }\n",
        hint="A min-heap of size k, or nth_element / sort.",
        editorial="Maintain a min-heap of size k. The root is the kth largest.",
    )
    _tc(db, kth.id, "6 2\n3 2 1 5 6 4\n", "5\n", True, 15, 0)
    _tc(db, kth.id, "9 4\n3 2 3 1 2 4 5 5 6\n", "4\n", True, 15, 1)
    _tc(db, kth.id, "1 1\n42\n", "42\n", False, 10, 2)

    hard = _p(
        db,
        slug="median-stream",
        title="Median of a Stream",
        difficulty="Hard",
        tags="heap,design",
        statement=(
            "Process a stream of integers. After every insertion print the median. "
            "If the count is even, print the average of the two middle values truncated toward zero "
            "(integer division).\n\n"
            "**Input**\nFirst line: q\nNext q lines: one integer each to insert."
        ),
        input_spec="q then q integers",
        output_spec="q lines of medians",
        constraints="1 ≤ q ≤ 5000",
        starter_python="q = int(input())\nfor _ in range(q):\n    x = int(input())\n    print(x)\n",
        starter_cpp="#include <bits/stdc++.h>\nusing namespace std; int main(){ int q; cin>>q; }\n",
        starter_java="import java.util.*;\npublic class Main { public static void main(String[] a){} }\n",
        hint="Two heaps: max-heap for the lower half, min-heap for the upper half.",
        editorial="Balance heaps so sizes differ by at most one. Median is top of the larger, or average.",
    )
    _tc(db, hard.id, "5\n1\n2\n3\n4\n5\n", "1\n1\n2\n2\n3\n", True, 20, 0)
    _tc(db, hard.id, "3\n5\n15\n1\n", "5\n10\n5\n", False, 20, 1)

    now = datetime.now(timezone.utc)
    weekly = Contest(
        slug="aether-weekly-01",
        title="Aether Weekly #01",
        description="A short live round. Contest submissions jump the priority queue so the leaderboard stays honest under load.",
        starts_at=now - timedelta(minutes=10),
        ends_at=now + timedelta(hours=6),
        is_public=True,
    )
    db.add(weekly)
    db.flush()
    db.add_all(
        [
            ContestProblem(contest_id=weekly.id, problem_id=two_sum.id, letter="A", points=100),
            ContestProblem(contest_id=weekly.id, problem_id=climb.id, letter="B", points=100),
            ContestProblem(contest_id=weekly.id, problem_id=isl.id, letter="C", points=150),
            ContestProblem(contest_id=weekly.id, problem_id=kth.id, letter="D", points=150),
        ]
    )

    upcoming = Contest(
        slug="grand-prix",
        title="Grand Prix Invitational",
        description="A longer set opening later today. Problems stay hidden until the start bell.",
        starts_at=now + timedelta(hours=8),
        ends_at=now + timedelta(hours=13),
        is_public=True,
    )
    db.add(upcoming)

    assess = Assessment(
        slug="northstar-oa",
        company="Northstar Labs",
        title="Backend Engineer OA",
        description=(
            "Timed take-home style screen. AI explainer and hints are locked for the duration. "
            "Tab switches, blurs, and paste events are stored as an integrity signal log for human review — "
            "not a hard cheat-detection guarantee."
        ),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=7),
        duration_minutes=90,
        lock_ai=True,
        invite_code="NORTHSTAR",
    )
    db.add(assess)
    db.flush()
    db.add_all(
        [
            AssessmentProblem(assessment_id=assess.id, problem_id=two_sum.id, points=100),
            AssessmentProblem(assessment_id=assess.id, problem_id=lru.id, points=150),
            AssessmentProblem(assessment_id=assess.id, problem_id=hard.id, points=200),
        ]
    )
    db.commit()
