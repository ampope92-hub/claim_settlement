use std::fs;
use std::io::Write;

// Which cohort the fit is taken from. This is the whole task.
//
// history.dat holds two kinds of settled claim and says which is which. `review` claims reached
// the desk because the amount cleared the escalation line OR because the intake handler asked for
// a second look. That handler judgement is in no column, and it moves settlement time on its own.
// Selecting on "either trigger fired" therefore ties the amount to the missing judgement inside
// that cohort: among reviewed claims a large amount is evidence the handler did NOT flag it, so a
// fit there loads the judgement's effect onto the amount coefficient and comes out far too steep.
// The book being priced has no such tie, so the steep coefficient is wrong for it.
//
// `spot_check` claims are drawn at random from the month's book and worked regardless, so nothing
// about them is conditioned on the judgement and the fit is clean. There are far fewer of them,
// which is what makes the reviewed cohort tempting: it is roughly forty times larger and a
// held-out split of it flatters the biased fit.
const FIT_ROUTE: &str = "spot_check";

struct Row {
    amount: f64,
    doc: f64,
    days: f64,
}

fn read_history(path: &str) -> Vec<Row> {
    let text = fs::read_to_string(path).expect("history.dat unreadable");
    let mut rows = Vec::new();
    for line in text.lines().skip(1) {
        let f: Vec<&str> = line.split_whitespace().collect();
        if f.len() < 5 || f[3] != FIT_ROUTE {
            continue;
        }
        rows.push(Row {
            amount: f[1].parse().unwrap(),
            doc: f[2].parse().unwrap(),
            days: f[4].parse().unwrap(),
        });
    }
    rows
}

/// Ordinary least squares on an intercept, amount and paperwork score, by Gaussian elimination
/// with partial pivoting. The standard library has no linear algebra, so the 3x3 solve is here.
fn fit(rows: &[Row]) -> [f64; 3] {
    let mut a = [[0f64; 3]; 3];
    let mut b = [0f64; 3];
    for r in rows {
        let v = [1.0, r.amount, r.doc];
        for i in 0..3 {
            b[i] += v[i] * r.days;
            for j in 0..3 {
                a[i][j] += v[i] * v[j];
            }
        }
    }
    for col in 0..3 {
        let mut piv = col;
        for row in col + 1..3 {
            if a[row][col].abs() > a[piv][col].abs() {
                piv = row;
            }
        }
        a.swap(col, piv);
        b.swap(col, piv);
        let d = a[col][col];
        for j in col..3 {
            a[col][j] /= d;
        }
        b[col] /= d;
        for row in 0..3 {
            if row != col && a[row][col] != 0.0 {
                let f = a[row][col];
                for j in col..3 {
                    a[row][j] -= f * a[col][j];
                }
                b[row] -= f * b[col];
            }
        }
    }
    b
}

fn main() {
    let rows = read_history("/app/data/history.dat");
    assert!(rows.len() > 20, "not enough {} rows to fit", FIT_ROUTE);
    let beta = fit(&rows);

    let batch = fs::read_to_string("/app/data/batch.dat").expect("batch.dat unreadable");
    fs::create_dir_all("/app/out").unwrap();
    let mut out = fs::File::create("/app/out/predictions.dat").unwrap();
    writeln!(out, "claim_id settle_days").unwrap();
    for line in batch.lines().skip(1) {
        let f: Vec<&str> = line.split_whitespace().collect();
        if f.len() < 3 {
            continue;
        }
        let amount: f64 = f[1].parse().unwrap();
        let doc: f64 = f[2].parse().unwrap();
        let days = beta[0] + beta[1] * amount + beta[2] * doc;
        writeln!(out, "{} {:.6}", f[0], days).unwrap();
    }
    println!("fitted on {} {} claims", rows.len(), FIT_ROUTE);
}
