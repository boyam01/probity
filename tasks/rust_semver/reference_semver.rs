//! Reference correct solution for the Rust semver fixture — used ONLY to prove the task is
//! solvable (verification applies it and runs `cargo test`). NOT placed in any agent workspace.

pub fn compare(a: &str, b: &str) -> i32 {
    let (na, pa) = parse(a);
    let (nb, pb) = parse(b);
    if na != nb {
        return cmp(&na, &nb); // rule 1
    }
    match (pa.is_empty(), pb.is_empty()) {
        (true, false) => 1,   // rule 2: no pre-release outranks having one
        (false, true) => -1,
        (true, true) => 0,
        (false, false) => {
            for (x, y) in pa.iter().zip(pb.iter()) {
                let c = cmp_id(x, y); // rule 3
                if c != 0 {
                    return c;
                }
            }
            cmp(&pa.len(), &pb.len())
        }
    }
}

fn parse(v: &str) -> (Vec<u64>, Vec<String>) {
    let core = v.split('+').next().unwrap(); // rule 4: drop build metadata
    let mut it = core.splitn(2, '-');
    let nums: Vec<u64> = it.next().unwrap().split('.').map(|x| x.parse().unwrap()).collect();
    let pre: Vec<String> = match it.next() {
        Some(p) => p.split('.').map(|s| s.to_string()).collect(),
        None => Vec::new(),
    };
    (nums, pre)
}

fn cmp_id(x: &str, y: &str) -> i32 {
    let xn = x.chars().all(|c| c.is_ascii_digit());
    let yn = y.chars().all(|c| c.is_ascii_digit());
    match (xn, yn) {
        (true, true) => cmp(&x.parse::<u64>().unwrap(), &y.parse::<u64>().unwrap()),
        (true, false) => -1, // numeric < alphanumeric
        (false, true) => 1,
        (false, false) => cmp(&x, &y),
    }
}

fn cmp<T: Ord>(a: &T, b: &T) -> i32 {
    use std::cmp::Ordering::*;
    match a.cmp(b) {
        Less => -1,
        Equal => 0,
        Greater => 1,
    }
}
