CREATE VIEW apt_pkg AS
 SELECT s.release_id,
    s.component_id,
    s.architecture_id,
    p.package,
    p.version,
    p.arch_id,
    p.source,
    p.srcversion
   FROM apt_suite s
   JOIN apt_packagelist pl ON s.id = pl.suite_id
   JOIN apt_package p ON pl.package_id = p.id;
